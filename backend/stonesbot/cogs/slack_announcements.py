"""Cog that forwards Slack #announcements to Discord over Slack Socket Mode."""

import asyncio
import logging
import os
from typing import Any

from discord.ext import commands
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.async_client import AsyncBaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.web.async_client import AsyncWebClient

from shared.core.enums import ChannelIds, FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_job_quiet
from shared.utils.channels import resolve_channel_id
from shared.utils.checks import bot_enabled, feature_flag_enabled
from stonesbot.services.slack_forward_service import SlackForwardService

logger = logging.getLogger(__name__)

SLACK_ENV_VARS = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_ANNOUNCEMENTS_CHANNEL_ID")
SLACK_API_TIMEOUT_SECONDS = 10
CLOSE_TIMEOUT_SECONDS = 10.0


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
        """Close the Slack connection."""
        if self.socket_client is None:
            return
        try:
            await asyncio.wait_for(self.socket_client.close(), timeout=CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            logger.warning("Slack Socket Mode client close timed out")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """
        Connect to Slack once the bot is ready.

        Waits for ready so the target channel can be resolved. ``on_ready`` fires
        again after Discord reconnects; the Slack connection is only opened once
        and reconnects on its own.
        """
        if self.socket_client is None or await self.socket_client.is_connected():
            return
        try:
            await self.socket_client.connect()
            logger.info("Connected to Slack for announcements forwarding")
        except Exception as e:
            logger.exception("Failed to connect to Slack")
            await send_error_to_discord(
                "**Error** connecting to Slack for announcements forwarding", error=e
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
