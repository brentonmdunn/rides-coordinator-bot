"""Cog that forwards Slack #announcements to Discord over Slack Socket Mode."""

import asyncio
import logging
import os
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from slack_sdk.errors import SlackApiError
from slack_sdk.http_retry.builtin_async_handlers import AsyncRateLimitErrorRetryHandler
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.async_client import AsyncBaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from shared.core.enums import ChannelIds, FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_cmd, log_job_quiet
from shared.utils.channels import resolve_channel_id
from shared.utils.checks import bot_enabled, feature_flag_enabled, is_admin
from stonesbot.services.slack_forward_service import (
    LinkForwardResult,
    LinkForwardStatus,
    SlackForwardService,
)

logger = logging.getLogger(__name__)

SLACK_ENV_VARS = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ANNOUNCEMENTS_CHANNEL_ID")
SLACK_API_TIMEOUT_SECONDS = 10
CLOSE_TIMEOUT_SECONDS = 10.0
SLACK_RATE_LIMIT_RETRIES = 2
CONNECT_RETRY_INITIAL_SECONDS = 30
CONNECT_RETRY_MAX_SECONDS = 15 * 60
# Slack errors that mean a token is wrong, not that Slack is having a bad day.
# Retrying these only floods the logs, so they stop the connection attempt.
PERMANENT_AUTH_ERRORS = frozenset(
    {
        "invalid_auth",
        "not_authed",
        "account_inactive",
        "token_revoked",
        "token_expired",
        "not_allowed_token_type",
        "missing_scope",
    }
)


# Replies to /forward-slack-message, by outcome. FORWARDED and ALREADY_FORWARDED
# get the Discord link appended; SLACK_ERROR gets Slack's error code.
LINK_FORWARD_REPLIES: dict[LinkForwardStatus, str] = {
    LinkForwardStatus.FORWARDED: "✅ Forwarded.",
    LinkForwardStatus.ALREADY_FORWARDED: "That message was already forwarded.",
    LinkForwardStatus.INVALID_LINK: (
        "❌ That isn't a Slack message link. In Slack, hover the message, click ⋯ → "
        "**Copy link**, and paste that."
    ),
    LinkForwardStatus.WRONG_CHANNEL: (
        "❌ That message isn't in the Slack announcements channel; only those can be forwarded."
    ),
    LinkForwardStatus.THREAD_REPLY: "❌ That's a reply in a thread; only top-level posts are forwarded.",
    LinkForwardStatus.NOT_FOUND: (
        "❌ Slack couldn't find that message. It may have been deleted, or be older than "
        "the workspace's message history allows."
    ),
    LinkForwardStatus.NOT_FORWARDABLE: (
        "❌ That's not a regular post (e.g. a join or bot message), so it isn't forwarded."
    ),
    LinkForwardStatus.NOTHING_TO_FORWARD: "That message has no text or files to forward.",
    LinkForwardStatus.NO_WEBHOOK: (
        "❌ StonesBot couldn't get its webhook in the announcements channel; it needs the "
        "Manage Webhooks permission there."
    ),
    LinkForwardStatus.SLACK_ERROR: "❌ Slack refused the request",
}


def link_forward_reply(result: LinkForwardResult) -> str:
    """The ephemeral reply for a /forward-slack-message outcome."""
    reply = LINK_FORWARD_REPLIES[result.status]
    if result.status == LinkForwardStatus.SLACK_ERROR:
        hint = (
            " (is the Slack app in the channel?)" if result.slack_error == "not_in_channel" else ""
        )
        return f"{reply}: `{result.slack_error}`{hint}"
    if result.jump_url:
        return f"{reply} {result.jump_url}"
    return reply


def _slack_error_code(error: Exception) -> str | None:
    """The Slack API error code (e.g. ``invalid_auth``) from a SlackApiError, else None."""
    if isinstance(error, SlackApiError):
        return error.response.get("error")
    return None


class SlackAnnouncements(commands.Cog):
    """
    Listens to a Slack channel over Socket Mode and mirrors it into Discord.

    Socket Mode opens an outbound websocket to Slack, so no public endpoint is
    needed. The feature is optional: if any Slack env var is unset, the cog
    logs one warning and does nothing.
    """

    def __init__(self, bot: commands.Bot):
        """
        Initialize the SlackAnnouncements cog.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot
        self.socket_client: SocketModeClient | None = None
        self.service: SlackForwardService | None = None
        self._connect_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        """Build the Slack clients from the environment, if configured."""
        values = {name: os.getenv(name, "").strip() for name in SLACK_ENV_VARS}
        missing = [name for name, value in values.items() if not value]
        if missing:
            logger.warning(
                "Slack announcements forwarding disabled; missing %s", ", ".join(missing)
            )
            return

        web_client = AsyncWebClient(
            token=values["SLACK_BOT_TOKEN"], timeout=SLACK_API_TIMEOUT_SECONDS
        )
        web_client.retry_handlers.append(
            AsyncRateLimitErrorRetryHandler(max_retry_count=SLACK_RATE_LIMIT_RETRIES)
        )
        self.service = SlackForwardService(
            bot=self.bot,
            slack_client=web_client,
            slack_bot_token=values["SLACK_BOT_TOKEN"],
            slack_channel_id=values["SLACK_ANNOUNCEMENTS_CHANNEL_ID"],
            discord_channel_id=resolve_channel_id(ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS),
        )
        self.socket_client = SocketModeClient(
            app_token=values["SLACK_APP_TOKEN"], web_client=web_client
        )
        self.socket_client.socket_mode_request_listeners.append(self._on_request)

    async def cog_unload(self) -> None:
        """Stop connecting and close the Slack connection."""
        if self._connect_task is not None:
            self._connect_task.cancel()
        if self.socket_client is None:
            return
        try:
            await asyncio.wait_for(self.socket_client.close(), timeout=CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("Slack Socket Mode client close timed out")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Start connecting to Slack once the bot is ready.

        Waits for ready so the target channel can be resolved. ``on_ready`` fires
        again after every Discord reconnect; only the first one starts the
        connection, which then reconnects on its own.
        """
        if self.socket_client is None or self._connect_task is not None:
            return
        self._connect_task = asyncio.create_task(self._connect())

    async def _connect(self) -> None:
        """
        Check both Slack tokens, then open the Socket Mode connection.

        ``SocketModeClient.connect()`` never gives up on its own: a bad token
        makes it log a traceback and retry every few seconds forever, unseen.
        So the websocket URL is requested here first, where a bad token is
        reported once and stops the attempt, and transient failures back off
        (reported on the first failure only). Once a URL is in hand,
        ``connect()`` takes over and handles later drops itself.
        """
        if self.socket_client is None or self.service is None:
            return
        await self._check_bot_token()

        delay = CONNECT_RETRY_INITIAL_SECONDS
        reported = False
        while True:
            try:
                self.socket_client.wss_uri = await self.socket_client.issue_new_wss_url()
                break
            except Exception as e:
                code = _slack_error_code(e)
                if code in PERMANENT_AUTH_ERRORS:
                    logger.exception("Slack rejected SLACK_APP_TOKEN (%s)", code)
                    await send_error_to_discord(
                        f"**Error** Slack rejected `SLACK_APP_TOKEN` (`{code}`); announcements "
                        "won't be forwarded until it's fixed and the app restarts",
                        error=e,
                    )
                    return
                logger.exception("Failed to reach Slack; retrying in %ss", delay)
                if not reported:
                    reported = True
                    await send_error_to_discord(
                        "**Error** connecting to Slack for announcements forwarding; retrying "
                        "in the background (only this first failure is reported)",
                        error=e,
                    )
            await asyncio.sleep(delay)
            delay = min(delay * 2, CONNECT_RETRY_MAX_SECONDS)

        await self.socket_client.connect()
        logger.info("Connected to Slack for announcements forwarding")

    async def _check_bot_token(self) -> None:
        """
        Report a bad SLACK_BOT_TOKEN up front.

        The connection itself uses the app token, so with a bad bot token
        announcements would still arrive and post, just quietly without author
        names, the Slack link or attachments.
        """
        if self.service is None:
            return
        try:
            await self.service.slack.auth_test()
        except Exception as e:
            code = _slack_error_code(e)
            if code not in PERMANENT_AUTH_ERRORS:
                logger.warning("Could not verify SLACK_BOT_TOKEN; continuing", exc_info=True)
                return
            logger.exception("Slack rejected SLACK_BOT_TOKEN (%s)", code)
            await send_error_to_discord(
                f"**Error** Slack rejected `SLACK_BOT_TOKEN` (`{code}`); announcements will "
                "post without author names, Slack links or attachments until it's fixed",
                error=e,
            )

    async def _on_request(
        self, client: AsyncBaseSocketModeClient, request: SocketModeRequest
    ) -> None:
        """Acknowledge every Socket Mode request, then forward message events."""
        await client.send_socket_mode_response(SocketModeResponse(envelope_id=request.envelope_id))
        if request.type != "events_api":
            return
        event = request.payload.get("event") or {}
        await self._forward(event)

    @app_commands.command(
        name="forward-slack-message",
        description="Forward a Slack #announcements post that the bridge missed.",
    )
    @app_commands.describe(url="Link to the Slack message (⋯ → Copy link in Slack)")
    @log_cmd
    @bot_enabled
    @feature_flag_enabled(FeatureFlagNames.SLACK_ANNOUNCEMENTS_FORWARDING)
    @is_admin()
    async def forward_slack_message(self, interaction: discord.Interaction, url: str) -> None:
        """
        Forward one Slack announcement by link, for posts made before the bridge ran.

        Admins only. Never pings. Later edits and deletes in Slack are mirrored to
        it like any live post.

        Args:
            interaction: The Discord interaction.
            url: A Slack message link.
        """
        if self.service is None:
            await interaction.response.send_message(
                "❌ Slack forwarding isn't configured (the `SLACK_*` env vars aren't set).",
                ephemeral=True,
            )
            return

        # Downloading attachments can take longer than Discord's 3s reply window.
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result = await self.service.forward_from_link(url)
        except Exception as e:
            logger.exception("Failed to forward Slack message by link")
            await send_error_to_discord(
                f"**Error** in `/forward-slack-message` for `{url}`", error=e
            )
            await interaction.followup.send(
                "❌ Something went wrong forwarding that message; it's been reported.",
                ephemeral=True,
            )
            return

        logger.info("/forward-slack-message %s: %s", url, result.status)
        await interaction.followup.send(link_forward_reply(result), ephemeral=True)

    @log_job_quiet
    @bot_enabled
    @feature_flag_enabled(FeatureFlagNames.SLACK_ANNOUNCEMENTS_FORWARDING, enable_logs=False)
    async def _forward(self, event: dict[str, Any]) -> None:
        """Hand one Slack event to the service, behind the kill switch and flag."""
        if self.service is not None:
            await self.service.handle_event(event)


async def setup(bot: commands.Bot) -> None:
    """Sets up the SlackAnnouncements cog."""
    await bot.add_cog(SlackAnnouncements(bot))
