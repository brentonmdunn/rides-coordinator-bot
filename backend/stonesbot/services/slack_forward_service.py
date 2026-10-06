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
from slack_sdk.web.async_client import AsyncWebClient

from shared.core.database import AsyncSessionLocal
from shared.core.enums import FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord
from shared.repositories.feature_flags_repository import FeatureFlagsRepository
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
# Discord JSON error code for a webhook that no longer exists.
UNKNOWN_WEBHOOK = 10015

# Message subtypes that are a new post worth forwarding. Everything else that
# isn't an edit or delete (joins, topic changes, bot_message, ...) is ignored.
NEW_POST_SUBTYPES = frozenset({None, "file_share", "thread_broadcast"})

# What a forwarded post may ping. Only @everyone/@here, and only on the first
# forward of a new post: never users or roles, and never on edits or reposts.
NO_PINGS = discord.AllowedMentions.none()
EVERYONE_PINGS = discord.AllowedMentions(
    everyone=True, users=False, roles=False, replied_user=False
)


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
        ``"<name> (via LSCC Slack)"``, trimmed to Discord's limit, or a generic name
        if the author's name contains a word Discord rejects in webhook names.
    """
    if any(word in author.name.casefold() for word in FORBIDDEN_USERNAME_SUBSTRINGS):
        return "Slack announcement"
    suffix = " (via LSCC Slack)"
    return author.name[: WEBHOOK_USERNAME_LIMIT - len(suffix)] + suffix


def too_large_note(file: dict[str, Any]) -> str:
    """Line telling Discord readers a file was left in Slack."""
    return f"📎 {file.get('name') or 'attachment'} (too large to attach here, see Slack)"


def download_failed_note(file: dict[str, Any]) -> str:
    """Line telling Discord readers a file couldn't be copied over."""
    return f"📎 {file.get('name') or 'attachment'} (couldn't be attached here, see Slack)"


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
                    await self._forward_new(event, await self._pings_enabled())
                elif subtype == "message_changed":
                    await self._forward_edit(event, await self._pings_enabled())
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

    async def _forward_new(self, message: dict[str, Any], pings: bool) -> None:
        """
        Post a new Slack message to Discord and record where it went.

        Args:
            message: The Slack message event.
            pings: Whether Slack's @channel/@here/@everyone ping in Discord.
        """
        ts = message["ts"]
        if is_thread_reply(message):
            logger.debug("Ignoring Slack thread reply %s", ts)
            return
        if await self._get_parts(ts):
            logger.info("Slack message %s was already forwarded; skipping", ts)
            return

        message_ids = await self._post_with_webhook(message, pings=pings, notify=pings)
        if not message_ids:
            return

        try:
            await self._save_parts(ts, message_ids)
        except Exception as e:
            # The post is up; only the mapping is missing. Say exactly what that costs.
            logger.exception("Failed to record forwarded Slack message %s", ts)
            await send_error_to_discord(
                f"**Error** recording forwarded Slack message `{ts}` (Discord messages "
                f"{', '.join(map(str, message_ids))}); later edits and deletes in Slack "
                "won't be mirrored for it",
                error=e,
            )
            return
        logger.info("Forwarded Slack message %s as %d Discord message(s)", ts, len(message_ids))

    async def _forward_edit(self, event: dict[str, Any], pings: bool) -> None:
        """
        Apply a Slack edit to the Discord messages posted for it.

        Edits never ping, even when they add a mass mention or turn into a
        repost; *pings* only decides how mass mentions are written.
        """
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

        if not await self._any_part_exists(parts):
            # A moderator deleted the Discord copy; an edit in Slack must not bring it back.
            logger.info(
                "Forwarded copy of Slack message %s was removed in Discord; ignoring edit", ts
            )
            async with AsyncSessionLocal() as session:
                await SlackForwardedMessageRepository.delete_parts(
                    session, self.slack_channel_id, ts
                )
                await session.commit()
            return

        plan = plan_files(message.get("files") or [], await self._size_limit())
        text = await self._render_text(message, plan.notes, bool(plan.attach), pings)
        chunks = split_message(text) or ([""] if plan.attach else [])

        if files_changed or len(chunks) != len(parts):
            # Attachments can't be swapped cleanly in place and parts can't be
            # inserted mid-channel, so post the new version and drop the old one.
            await self._repost(message, parts, pings)
            return

        for row, chunk in zip(parts, chunks, strict=True):
            try:
                await webhook.edit_message(
                    int(row.discord_message_id),
                    content=chunk or None,
                    allowed_mentions=NO_PINGS,
                )
            except discord.NotFound as e:
                if e.code != UNKNOWN_WEBHOOK:
                    logger.info(
                        "Forwarded Discord message %s is gone; skipping its edit",
                        row.discord_message_id,
                    )
                    continue
                # The webhook was deleted, and a new one can't edit the old one's
                # messages, so post the edited version fresh instead.
                logger.warning("Slack forwarding webhook is gone; reposting %s", ts)
                self._webhook = None
                await self._repost(message, parts, pings)
                return
        logger.info("Applied edit to forwarded Slack message %s", ts)

    async def _forward_delete(self, ts: str) -> None:
        """Delete the Discord messages posted for a deleted Slack message."""
        parts = await self._get_parts(ts)
        if not parts:
            logger.info("Deleted Slack message %s was never forwarded; skipping", ts)
            return

        failed = await self._delete_discord_messages([int(p.discord_message_id) for p in parts])
        if failed:
            # Keep the rows so the leftover messages can still be found and removed.
            await send_error_to_discord(
                f"**Error** deleting forwarded Slack message `{ts}`: Discord messages "
                f"{', '.join(map(str, failed))} could not be deleted; remove them by hand"
            )
            return
        async with AsyncSessionLocal() as session:
            await SlackForwardedMessageRepository.delete_parts(session, self.slack_channel_id, ts)
            await session.commit()
        logger.info("Deleted forwarded Slack message %s", ts)

    async def _repost(self, message: dict[str, Any], parts: list, pings: bool) -> None:
        """
        Replace a forwarded message by posting the new version, then deleting the old.

        Ordered so a failure at any step leaves exactly one version visible and
        mapped: the new version goes out first, the mapping is switched to it
        (or the new version is withdrawn if that fails), and only then is the
        old version deleted. The new version never pings: everyone was already
        notified when the post first went out.
        """
        ts = message["ts"]
        message_ids = await self._post_with_webhook(message, pings=pings, notify=False)
        if message_ids is None:
            return

        try:
            await self._save_parts(ts, message_ids, replace=True)
        except Exception:
            await self._delete_discord_messages(message_ids)
            raise

        old_ids = [int(p.discord_message_id) for p in parts]
        failed = await self._delete_discord_messages(old_ids)
        if failed:
            await send_error_to_discord(
                f"**Error** reposting edited Slack message `{ts}`: the old Discord messages "
                f"{', '.join(map(str, failed))} could not be deleted; remove them by hand"
            )
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

    async def _post_with_webhook(
        self, message: dict[str, Any], pings: bool, notify: bool
    ) -> list[int] | None:
        """
        Post a Slack message through the forwarding webhook.

        If the cached webhook was deleted in Discord, a new one is found or
        created and the post is retried once.

        Args:
            message: The Slack message.
            pings: Write mass mentions as Discord's @everyone/@here.
            notify: Let those mentions actually ping.

        Returns:
            The posted Discord message ids (empty if there was nothing to
            forward), or None if no webhook is available.
        """
        for attempt in range(2):
            webhook = await self._get_webhook()
            if webhook is None:
                return None
            try:
                message_ids = await self._post(webhook, message, pings, notify)
            except discord.NotFound as e:
                if e.code != UNKNOWN_WEBHOOK or attempt:
                    raise
                logger.warning("Slack forwarding webhook was deleted; getting a new one")
                self._webhook = None
                continue
            if not message_ids:
                logger.info("Slack message %s has nothing to forward", message["ts"])
            return message_ids
        return None

    async def _size_limit(self) -> int:
        """Discord's upload limit for the target channel's guild, in bytes."""
        channel = self.bot.get_channel(self.discord_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel.guild.filesize_limit
        return discord.utils.DEFAULT_FILE_SIZE_LIMIT_BYTES

    async def _post(
        self, webhook: discord.Webhook, message: dict[str, Any], pings: bool, notify: bool
    ) -> list[int]:
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

        attached_files, attachments, download_error = await self._download_files(plan.attach)
        failed_files = [f for f in plan.attach if f not in attached_files]
        notes = plan.notes + [download_failed_note(f) for f in failed_files]
        if download_error is not None:
            # The announcement still goes out; only the files are left behind.
            await send_error_to_discord(
                f"**Error** downloading {len(failed_files)} file(s) for Slack message "
                f"`{message['ts']}`; posted without them",
                error=download_error,
            )

        text = await self._render_text(message, notes, bool(attachments), pings)
        try:
            return await self._send(webhook, text, attachments, author, notify)
        except discord.HTTPException as e:
            if e.status != HTTP_PAYLOAD_TOO_LARGE or not attachments:
                raise
            logger.warning("Discord rejected attachments as too large; posting without them")
            notes += [too_large_note(f) for f in attached_files]
            text = await self._render_text(message, notes, False, pings)
            return await self._send(webhook, text, [], author, notify)

    async def _send(
        self,
        webhook: discord.Webhook,
        text: str,
        attachments: list[discord.File],
        author: SlackAuthor,
        notify: bool = False,
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
                    allowed_mentions=EVERYONE_PINGS if notify else NO_PINGS,
                    wait=True,
                    **kwargs,
                )
                sent.append(sent_message.id)
        except discord.HTTPException:
            await self._delete_discord_messages(sent)
            raise
        return sent

    async def _delete_discord_messages(self, message_ids: list[int]) -> list[int]:
        """
        Delete forwarded messages, skipping any that are already gone.

        Goes through the webhook first. If that can't reach a message (the
        webhook that posted it was deleted, or it's already gone), falls back to
        deleting it as StonesBot, which needs Manage Messages.

        Returns:
            Ids of the messages that could not be deleted and still exist.
        """
        if not message_ids:
            return []

        webhook = await self._get_webhook()
        failed: list[int] = []
        for message_id in message_ids:
            if webhook is None:
                if not await self._delete_as_bot(message_id):
                    failed.append(message_id)
                continue
            try:
                await webhook.delete_message(message_id)
            except discord.NotFound as e:
                if e.code == UNKNOWN_WEBHOOK:
                    self._webhook = None
                if not await self._delete_as_bot(message_id):
                    failed.append(message_id)
            except discord.HTTPException:
                logger.exception("Failed to delete forwarded Discord message %s", message_id)
                failed.append(message_id)
        return failed

    async def _any_part_exists(self, parts: list) -> bool:
        """
        Whether any of a forwarded message's Discord parts still exists.

        Asks the webhook first and falls back to reading the channel as
        StonesBot when the webhook that posted them is gone. Errors other than
        "not found" count as existing, so a Discord hiccup never makes the
        bridge forget a message.
        """
        channel = self.bot.get_channel(self.discord_channel_id)
        for row in parts:
            message_id = int(row.discord_message_id)
            try:
                webhook = await self._get_webhook()
                if webhook is not None:
                    try:
                        await webhook.fetch_message(message_id)
                        return True
                    except discord.NotFound as e:
                        if e.code != UNKNOWN_WEBHOOK:
                            continue
                        self._webhook = None
                if isinstance(channel, discord.TextChannel):
                    await channel.fetch_message(message_id)
                return True
            except discord.NotFound:
                continue
            except discord.HTTPException:
                logger.exception("Could not check forwarded Discord message %s", message_id)
                return True
        return False

    async def _delete_as_bot(self, message_id: int) -> bool:
        """
        Delete a message as StonesBot rather than through the webhook.

        Returns:
            True if the message is gone (deleted now or already), False if it
            still exists.
        """
        channel = self.bot.get_channel(self.discord_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False
        try:
            await channel.get_partial_message(message_id).delete()
            logger.info("Deleted forwarded Discord message %s as StonesBot", message_id)
            return True
        except discord.NotFound:
            logger.info("Forwarded Discord message %s was already deleted", message_id)
            return True
        except discord.HTTPException:
            logger.exception(
                "Failed to delete forwarded Discord message %s (StonesBot needs Manage Messages)",
                message_id,
            )
            return False

    # ------------------------------------------------------------------
    # Slack side
    # ------------------------------------------------------------------

    async def _get_author(self, user_id: str | None) -> SlackAuthor:
        """A Slack user's display name and avatar, or a generic author if unknown."""
        if user_id:
            author = await self._lookup_user(user_id)
            if author is not None:
                return author
        return SlackAuthor(FALLBACK_AUTHOR_NAME, None)

    async def _lookup_user(self, user_id: str) -> SlackAuthor | None:
        """
        Look up a Slack user's display name and avatar, cached for an hour.

        Returns:
            The user, or None if the lookup failed. Failures are logged, never
            raised: names are cosmetic and must not cost the announcement.
        """
        cached = self._authors.get(user_id)
        if cached and time.monotonic() - cached[0] < AUTHOR_CACHE_TTL_SECONDS:
            return cached[1]

        try:
            response = await self.slack.users_info(user=user_id)
        except Exception:
            logger.exception("Failed to look up Slack user %s", user_id)
            return None

        user = response.get("user") or {}
        profile = user.get("profile") or {}
        name = profile.get("display_name") or profile.get("real_name") or user.get("name")
        if not name:
            return None
        author = SlackAuthor(name, profile.get("image_192"))
        self._authors[user_id] = (time.monotonic(), author)
        return author

    async def _render_text(
        self, message: dict[str, Any], notes: list[str], has_attachments: bool, pings: bool
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
            user = await self._lookup_user(user_id)
            if user is not None:
                names[user_id] = user.name
        lines = [
            line
            for line in (slack_to_discord(raw_text, names, pings=pings).strip(), *notes)
            if line
        ]
        if not lines and not has_attachments:
            return ""

        permalink = await self._get_permalink(message["ts"])
        if permalink:
            lines.append(permalink_line(permalink))
        return "\n".join(lines)

    async def _pings_enabled(self) -> bool:
        """
        Whether Slack's mass mentions should ping in Discord.

        Fails closed: if the flag can't be read, nothing pings.
        """
        try:
            async with AsyncSessionLocal() as session:
                enabled = await FeatureFlagsRepository.get_feature_flag_status(
                    session, FeatureFlagNames.SLACK_ANNOUNCEMENTS_PINGS
                )
        except Exception:
            logger.exception("Failed to read the Slack announcements pings flag")
            return False
        return bool(enabled)

    async def _get_permalink(self, ts: str) -> str | None:
        """Link to the original Slack message, or None if Slack can't provide one."""
        try:
            response = await self.slack.chat_getPermalink(
                channel=self.slack_channel_id, message_ts=ts
            )
        except Exception:
            logger.exception("Failed to get permalink for Slack message %s", ts)
            return None
        return response.get("permalink")

    async def _resolve_file(self, file: dict[str, Any]) -> dict[str, Any]:
        """Fetch a file's full metadata when the event only carries a stub."""
        if file.get("file_access") != "check_file_info":
            return file
        try:
            response = await self.slack.files_info(file=file["id"])
        except Exception:
            # Without full info the download fails and the file gets a note instead.
            logger.exception("Failed to look up Slack file %s", file.get("id"))
            return file
        return response.get("file") or file

    async def _download_files(
        self, files: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[discord.File], Exception | None]:
        """
        Download private Slack files so they can be re-uploaded to Discord.

        Each file is tried on its own; one that fails is logged and left out
        rather than failing the whole announcement. Slack answers a download
        it won't authorize with its HTML sign-in page (status 200), which is
        what happens when the app is missing the ``files:read`` scope, so that
        counts as a failure too.

        Returns:
            The files that downloaded, their ``discord.File`` objects (same
            order), and the first error hit, if any.
        """
        downloaded: list[dict[str, Any]] = []
        attachments: list[discord.File] = []
        first_error: Exception | None = None
        if not files:
            return downloaded, attachments, first_error

        headers = {"Authorization": f"Bearer {self.slack_bot_token}"}
        async with httpx.AsyncClient(
            timeout=FILE_DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            for file in files:
                try:
                    url = file.get("url_private_download") or file.get("url_private")
                    if not url:
                        raise RuntimeError(f"Slack file {file.get('id')} has no download URL")
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("text/html") and file.get("filetype") != "html":
                        raise RuntimeError(
                            f"Slack returned a sign-in page for file {file.get('id')}; "
                            "check the Slack app has the files:read scope"
                        )
                except Exception as e:
                    logger.exception("Failed to download Slack file %s", file.get("id"))
                    first_error = first_error or e
                    continue
                downloaded.append(file)
                attachments.append(
                    discord.File(io.BytesIO(response.content), filename=file.get("name") or "file")
                )
        return downloaded, attachments, first_error

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
