"""
Service that mirrors a Slack channel into a Discord channel.

New Slack posts are re-posted in Discord through a webhook that StonesBot owns,
under the Slack author's name and avatar. Each Discord message is recorded
against the Slack message's ts so later edits and deletes in Slack can be
applied to the same Discord messages. Called by the `SlackAnnouncements` cog,
which receives events from Slack over Socket Mode.
"""

import asyncio
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import discord
import httpx
from discord.ext.commands import Bot
from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from shared.core.database import AsyncSessionLocal
from shared.core.error_reporter import send_error_to_discord
from stonesbot.repositories.slack_forwarded_message_repository import (
    SlackForwardedMessageRepository,
)
from stonesbot.utils.slack_format import extract_user_ids, slack_to_discord, split_message

logger = logging.getLogger(__name__)

WEBHOOK_NAME = "Slack Announcements"
# Discord caps webhook usernames at 80 characters and rejects any containing these.
WEBHOOK_USERNAME_LIMIT = 80
FORBIDDEN_USERNAME_SUBSTRINGS = ("discord", "clyde")
FALLBACK_AUTHOR_NAME = "Slack"
DISCORD_MAX_FILES_PER_MESSAGE = 10
FILE_DOWNLOAD_TIMEOUT_SECONDS = 30.0
AUTHOR_CACHE_TTL_SECONDS = 3600
HTTP_PAYLOAD_TOO_LARGE = 413

# Message subtypes that are a new post worth forwarding. Everything else that
# isn't an edit or delete (joins, topic changes, bot_message, ...) is ignored.
NEW_POST_SUBTYPES = frozenset({None, "file_share", "thread_broadcast"})


@dataclass(frozen=True)
class SlackAuthor:
    """Who posted a Slack message, as shown on the forwarded Discord message."""

    name: str
    avatar_url: str | None


@dataclass
class FilePlan:
    """Which of a message's Slack files get attached, and notes for the rest."""

    attach: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def is_thread_reply(message: dict[str, Any]) -> bool:
    """
    Whether a Slack message is a reply inside a thread (and not also sent to the channel).

    Args:
        message: A Slack message payload.

    Returns:
        True for thread replies that should not be forwarded.
    """
    thread_ts = message.get("thread_ts")
    return (
        thread_ts is not None
        and thread_ts != message.get("ts")
        and message.get("subtype") != "thread_broadcast"
    )


def file_ids(message: dict[str, Any]) -> list[str]:
    """Ids of the files attached to a Slack message, in order."""
    return [f["id"] for f in message.get("files") or [] if "id" in f]


def webhook_username(author: SlackAuthor) -> str:
    """
    Build the username a forwarded message is posted under.

    Args:
        author: The Slack author.

    Returns:
        ``"<name> (via Slack)"``, trimmed to Discord's limit, or a generic name
        if the author's name contains a word Discord rejects in webhook names.
    """
    if any(word in author.name.casefold() for word in FORBIDDEN_USERNAME_SUBSTRINGS):
        return "Slack announcement"
    suffix = " (via Slack)"
    return author.name[: WEBHOOK_USERNAME_LIMIT - len(suffix)] + suffix


def too_large_note(file: dict[str, Any]) -> str:
    """Line telling Discord readers a file was left in Slack."""
    return f"📎 {file.get('name') or 'attachment'} (too large to attach here, see Slack)"


def permalink_line(permalink: str) -> str:
    """
    Small grey "View in Slack" line linking to the original message.

    ``-#`` is Discord's subtext markdown; the angle brackets around the URL stop
    Discord from adding a link preview.
    """
    return f"-# [View in Slack](<{permalink}>)"


def plan_files(files: list[dict[str, Any]], size_limit: int) -> FilePlan:
    """
    Decide which Slack files to attach and which only get a note.

    Deterministic from the files' metadata, so an edit can rebuild the same
    notes without downloading anything again.

    Args:
        files: The ``files`` list from a Slack message.
        size_limit: Discord's upload limit for the target guild, in bytes.

    Returns:
        The files to download and attach, plus a note line for each one that
        is skipped (too large, past Discord's per-message limit, or hosted
        outside Slack, which gets a link instead).
    """
    plan = FilePlan()
    for file in files:
        mode = file.get("mode")
        if mode == "tombstone":
            continue
        if mode == "external":
            url = file.get("url_private") or file.get("permalink")
            name = file.get("name") or file.get("title") or "attachment"
            plan.notes.append(f"📎 [{name}]({url})" if url else f"📎 {name}")
            continue
        if file.get("size", 0) > size_limit or len(plan.attach) >= DISCORD_MAX_FILES_PER_MESSAGE:
            plan.notes.append(too_large_note(file))
            continue
        plan.attach.append(file)
    return plan


class SlackForwardService:
    """Forwards new, edited and deleted Slack messages to a Discord channel."""

    def __init__(
        self,
        bot: Bot,
        slack_client: AsyncWebClient,
        slack_bot_token: str,
        slack_channel_id: str,
        discord_channel_id: int,
    ):
        """
        Initialize the service.

        Args:
            bot: The Discord bot that owns the webhook.
            slack_client: Slack Web API client authenticated as the Slack app.
            slack_bot_token: The Slack bot token, for downloading private files.
            slack_channel_id: The Slack channel to mirror; events from any other
                channel are ignored.
            discord_channel_id: The Discord channel to post in.
        """
        self.bot = bot
        self.slack = slack_client
        self.slack_bot_token = slack_bot_token
        self.slack_channel_id = slack_channel_id
        self.discord_channel_id = discord_channel_id
        self._webhook: discord.Webhook | None = None
        self._authors: dict[str, tuple[float, SlackAuthor]] = {}
        # Slack delivers events concurrently; an edit must not race the post it edits.
        self._lock = asyncio.Lock()

    async def handle_event(self, event: dict[str, Any]) -> None:
        """
        Apply one Slack ``message`` event to Discord.

        Never raises: failures are logged and reported to the error channel so
        one bad event can't stop the listener.

        Args:
            event: The ``event`` object from a Slack Events API payload.
        """
        if event.get("type") != "message" or event.get("channel") != self.slack_channel_id:
            return

        subtype = event.get("subtype")
        try:
            async with self._lock:
                if subtype in NEW_POST_SUBTYPES:
                    await self._forward_new(event)
                elif subtype == "message_changed":
                    await self._forward_edit(event)
                elif subtype == "message_deleted":
                    await self._forward_delete(event["deleted_ts"])
                else:
                    logger.debug("Ignoring Slack message subtype %s", subtype)
        except Exception as e:
            logger.exception("Failed to forward Slack %s event", subtype or "message")
            await send_error_to_discord(
                f"**Error** forwarding a Slack announcement ({subtype or 'new post'})",
                error=e,
            )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def _forward_new(self, message: dict[str, Any]) -> None:
        """Post a new Slack message to Discord and record where it went."""
        ts = message["ts"]
        if is_thread_reply(message):
            logger.debug("Ignoring Slack thread reply %s", ts)
            return
        if await self._get_parts(ts):
            logger.info("Slack message %s was already forwarded; skipping", ts)
            return

        webhook = await self._get_webhook()
        if webhook is None:
            return

        message_ids = await self._post(webhook, message)
        if not message_ids:
            logger.info("Slack message %s has nothing to forward", ts)
            return
        await self._save_parts(ts, message_ids)
        logger.info("Forwarded Slack message %s as %d Discord message(s)", ts, len(message_ids))

    async def _forward_edit(self, event: dict[str, Any]) -> None:
        """Apply a Slack edit to the Discord messages posted for it."""
        message = event["message"]
        ts = message["ts"]
        if message.get("subtype") == "tombstone":
            # A deleted message that still has thread replies arrives as an edit.
            await self._forward_delete(ts)
            return
        if is_thread_reply(message):
            return

        parts = await self._get_parts(ts)
        if not parts:
            logger.info("Edited Slack message %s was never forwarded; skipping", ts)
            return

        previous = event.get("previous_message") or {}
        files_changed = file_ids(message) != file_ids(previous)
        if message.get("text") == previous.get("text") and not files_changed:
            # Slack also sends message_changed for reply counts, unfurls, etc.
            logger.debug("Slack message %s changed without new text or files", ts)
            return

        webhook = await self._get_webhook()
        if webhook is None:
            return

        plan = plan_files(message.get("files") or [], await self._size_limit())
        text = await self._render_text(message, plan.notes, bool(plan.attach))
        chunks = split_message(text) or ([""] if plan.attach else [])

        if files_changed or len(chunks) != len(parts):
            # Attachments can't be swapped cleanly in place and parts can't be
            # inserted mid-channel, so post the new version and drop the old one.
            await self._repost(webhook, message, parts)
            return

        for row, chunk in zip(parts, chunks, strict=True):
            await webhook.edit_message(
                int(row.discord_message_id),
                content=chunk or None,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        logger.info("Applied edit to forwarded Slack message %s", ts)

    async def _forward_delete(self, ts: str) -> None:
        """Delete the Discord messages posted for a deleted Slack message."""
        parts = await self._get_parts(ts)
        if not parts:
            logger.info("Deleted Slack message %s was never forwarded; skipping", ts)
            return

        webhook = await self._get_webhook()
        if webhook is None:
            return

        await self._delete_discord_messages(webhook, [int(p.discord_message_id) for p in parts])
        async with AsyncSessionLocal() as session:
            await SlackForwardedMessageRepository.delete_parts(session, self.slack_channel_id, ts)
            await session.commit()
        logger.info("Deleted forwarded Slack message %s", ts)

    async def _repost(self, webhook: discord.Webhook, message: dict[str, Any], parts: list) -> None:
        """
        Replace a forwarded message by posting the new version, then deleting the old.

        The new version goes out first so a failed send never leaves Discord
        without the announcement.
        """
        ts = message["ts"]
        message_ids = await self._post(webhook, message)
        await self._delete_discord_messages(webhook, [int(p.discord_message_id) for p in parts])
        await self._save_parts(ts, message_ids, replace=True)
        logger.info("Reposted edited Slack message %s as %d message(s)", ts, len(message_ids))

    # ------------------------------------------------------------------
    # Discord side
    # ------------------------------------------------------------------

    async def _get_webhook(self) -> discord.Webhook | None:
        """
        Find StonesBot's forwarding webhook in the target channel, creating it if missing.

        Returns:
            The webhook, or None if the channel is unavailable or the bot lacks
            Manage Webhooks (both are logged and reported).
        """
        if self._webhook is not None:
            return self._webhook

        channel = self.bot.get_channel(self.discord_channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("Slack forwarding channel %s not found", self.discord_channel_id)
            return None

        bot_user_id = self.bot.user.id if self.bot.user else None
        try:
            for hook in await channel.webhooks():
                if (
                    hook.name == WEBHOOK_NAME
                    and hook.token
                    and hook.user is not None
                    and hook.user.id == bot_user_id
                ):
                    self._webhook = hook
                    return hook
            self._webhook = await channel.create_webhook(
                name=WEBHOOK_NAME, reason="Forward Slack #announcements"
            )
            logger.info("Created Slack forwarding webhook in channel %s", channel.id)
            return self._webhook
        except discord.Forbidden as e:
            logger.exception("StonesBot needs Manage Webhooks in channel %s", channel.id)
            await send_error_to_discord(
                f"**Error** forwarding Slack announcements: StonesBot needs the "
                f"Manage Webhooks permission in <#{channel.id}>",
                error=e,
            )
            return None

    async def _size_limit(self) -> int:
        """Discord's upload limit for the target channel's guild, in bytes."""
        channel = self.bot.get_channel(self.discord_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel.guild.filesize_limit
        return discord.utils.DEFAULT_FILE_SIZE_LIMIT_BYTES

    async def _post(self, webhook: discord.Webhook, message: dict[str, Any]) -> list[int]:
        """
        Post a Slack message through the webhook.

        Text longer than Discord's limit is split into several messages, with
        any attachments on the last one. If Discord rejects the attachments as
        too large, the message is posted again without them.

        Returns:
            The ids of the posted Discord messages, in order (empty if the Slack
            message had nothing to forward).
        """
        author = await self._get_author(message.get("user"))
        files = [await self._resolve_file(f) for f in message.get("files") or []]
        plan = plan_files(files, await self._size_limit())

        text = await self._render_text(message, plan.notes, bool(plan.attach))
        attachments = await self._download_files(plan.attach)
        try:
            return await self._send(webhook, text, attachments, author)
        except discord.HTTPException as e:
            if e.status != HTTP_PAYLOAD_TOO_LARGE or not attachments:
                raise
            logger.warning("Discord rejected attachments as too large; posting without them")
            notes = plan.notes + [too_large_note(f) for f in plan.attach]
            text = await self._render_text(message, notes, has_attachments=False)
            return await self._send(webhook, text, [], author)

    async def _send(
        self,
        webhook: discord.Webhook,
        text: str,
        attachments: list[discord.File],
        author: SlackAuthor,
    ) -> list[int]:
        """Send text (split as needed) and attachments, deleting partial sends on failure."""
        chunks = split_message(text) or ([""] if attachments else [])
        sent: list[int] = []
        try:
            for i, chunk in enumerate(chunks):
                kwargs: dict[str, Any] = {}
                if chunk:
                    kwargs["content"] = chunk
                if attachments and i == len(chunks) - 1:
                    kwargs["files"] = attachments
                sent_message = await webhook.send(
                    username=webhook_username(author),
                    avatar_url=author.avatar_url,
                    allowed_mentions=discord.AllowedMentions.none(),
                    wait=True,
                    **kwargs,
                )
                sent.append(sent_message.id)
        except discord.HTTPException:
            await self._delete_discord_messages(webhook, sent)
            raise
        return sent

    async def _delete_discord_messages(
        self, webhook: discord.Webhook, message_ids: list[int]
    ) -> None:
        """Delete webhook messages, skipping any that are already gone."""
        for message_id in message_ids:
            try:
                await webhook.delete_message(message_id)
            except discord.NotFound:
                logger.info("Forwarded Discord message %s was already deleted", message_id)

    # ------------------------------------------------------------------
    # Slack side
    # ------------------------------------------------------------------

    async def _get_author(self, user_id: str | None) -> SlackAuthor:
        """Look up a Slack user's display name and avatar, cached for an hour."""
        if not user_id:
            return SlackAuthor(FALLBACK_AUTHOR_NAME, None)

        cached = self._authors.get(user_id)
        if cached and time.monotonic() - cached[0] < AUTHOR_CACHE_TTL_SECONDS:
            return cached[1]

        try:
            response = await self.slack.users_info(user=user_id)
        except SlackApiError:
            logger.exception("Failed to look up Slack user %s", user_id)
            return SlackAuthor(FALLBACK_AUTHOR_NAME, None)

        user = response.get("user") or {}
        profile = user.get("profile") or {}
        name = (
            profile.get("display_name")
            or profile.get("real_name")
            or user.get("name")
            or FALLBACK_AUTHOR_NAME
        )
        author = SlackAuthor(name, profile.get("image_192"))
        self._authors[user_id] = (time.monotonic(), author)
        return author

    async def _render_text(
        self, message: dict[str, Any], notes: list[str], has_attachments: bool
    ) -> str:
        """
        Build the Discord text for a Slack message.

        Slack text converted to Discord markdown, then the attachment notes,
        then a small "View in Slack" link. A message with no text, notes or
        attachments renders as empty so it isn't forwarded as a bare link.
        """
        raw_text = message.get("text") or ""
        names = {}
        for user_id in extract_user_ids(raw_text):
            names[user_id] = (await self._get_author(user_id)).name
        lines = [line for line in (slack_to_discord(raw_text, names).strip(), *notes) if line]
        if not lines and not has_attachments:
            return ""

        permalink = await self._get_permalink(message["ts"])
        if permalink:
            lines.append(permalink_line(permalink))
        return "\n".join(lines)

    async def _get_permalink(self, ts: str) -> str | None:
        """Link to the original Slack message, or None if Slack can't provide one."""
        try:
            response = await self.slack.chat_getPermalink(
                channel=self.slack_channel_id, message_ts=ts
            )
        except SlackApiError:
            logger.exception("Failed to get permalink for Slack message %s", ts)
            return None
        return response.get("permalink")

    async def _resolve_file(self, file: dict[str, Any]) -> dict[str, Any]:
        """Fetch a file's full metadata when the event only carries a stub."""
        if file.get("file_access") != "check_file_info":
            return file
        response = await self.slack.files_info(file=file["id"])
        return response.get("file") or file

    async def _download_files(self, files: list[dict[str, Any]]) -> list[discord.File]:
        """
        Download private Slack files so they can be re-uploaded to Discord.

        Raises:
            RuntimeError: If Slack answers with its HTML sign-in page, which is
                what happens when the app is missing the ``files:read`` scope.
        """
        if not files:
            return []

        attachments = []
        headers = {"Authorization": f"Bearer {self.slack_bot_token}"}
        async with httpx.AsyncClient(
            timeout=FILE_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            for file in files:
                url = file.get("url_private_download") or file.get("url_private")
                if not url:
                    logger.warning("Slack file %s has no download URL; skipping", file.get("id"))
                    continue
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("text/html") and file.get("filetype") != "html":
                    raise RuntimeError(
                        f"Slack returned a sign-in page for file {file.get('id')}; "
                        "check the Slack app has the files:read scope"
                    )
                attachments.append(
                    discord.File(io.BytesIO(response.content), filename=file.get("name") or "file")
                )
        return attachments

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def _get_parts(self, ts: str) -> list:
        """Rows recording the Discord messages posted for a Slack message."""
        async with AsyncSessionLocal() as session:
            parts = await SlackForwardedMessageRepository.get_parts(
                session, self.slack_channel_id, ts
            )
            session.expunge_all()
            return parts

    async def _save_parts(self, ts: str, message_ids: list[int], replace: bool = False) -> None:
        """Record the Discord messages posted for a Slack message."""
        async with AsyncSessionLocal() as session:
            if replace:
                await SlackForwardedMessageRepository.delete_parts(
                    session, self.slack_channel_id, ts
                )
            for part, message_id in enumerate(message_ids):
                await SlackForwardedMessageRepository.add(
                    session,
                    slack_channel_id=self.slack_channel_id,
                    slack_ts=ts,
                    part=part,
                    discord_channel_id=str(self.discord_channel_id),
                    discord_message_id=str(message_id),
                )
            await session.commit()
