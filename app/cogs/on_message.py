"""Cog for handling reactions."""

import discord
from discord.ext import commands

from app.cogs.locations import Locations
from app.core.enums import (
    ChannelIds,
)
from app.services.check_rides_service import CheckRidesService


class OnMessage(commands.Cog):
    """Cog for handling reaction events on Discord messages.

    This cog monitors reaction additions and removals to trigger various automated
    behaviors such as logging reactions, managing event threads, creating ride
    coordination channels, and notifying about late ride requests.

    Attributes:
        bot: The Discord bot instance.
        locations_cog: Reference to the Locations cog for location lookups.
    """

    def __init__(
        self,
        bot: commands.Bot,
        check_rides_service: CheckRidesService,
    ):
        """Initialize the OnMessage cog.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot
        self.locations_cog: Locations | None = None
        self.check_rides_service: CheckRidesService | None = check_rides_service

    async def cog_load(self):
        """Wait until the bot is ready to get the cog."""
        self.locations_cog = self.bot.get_cog("Locations")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handles when a message is sent."""
        if message.author.bot:
            return

        await self.check_rides_service.check_pings(message, ChannelIds.BOT_STUFF__BOTS)


async def setup(bot: commands.Bot):
    check_rides_service = CheckRidesService(bot)
    await bot.add_cog(OnMessage(bot, check_rides_service=check_rides_service))
