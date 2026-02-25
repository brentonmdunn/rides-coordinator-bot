"""cogs/ask_drivers.py"""

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.enums import (
    AskRidesMessage,
    ChannelIds,
    DaysOfWeek,
    FeatureFlagNames,
)
from bot.core.logger import log_cmd
from bot.services.driver_service import DriverService
from bot.utils.autocomplete import lscc_day_autocomplete
from bot.utils.cache import warm_ask_drivers_message_cache
from bot.utils.channel_whitelist import (
    BOT_TESTING_CHANNELS,
    cmd_is_allowed,
)
from bot.utils.checks import feature_flag_enabled

DAY_TO_EVENT: dict[str, AskRidesMessage] = {
    "sunday": AskRidesMessage.SUNDAY_SERVICE,
    "friday": AskRidesMessage.FRIDAY_FELLOWSHIP,
}


class AskDrivers(commands.Cog):
    """Cog for asking drivers for availability."""

    def __init__(self, bot: commands.Bot, driver_service):
        """Initialize the AskDrivers cog."""

        self.bot = bot
        self.driver_service = driver_service

    @discord.app_commands.command(
        name="ask-drivers",
        description="Pings drivers to see who is available.",
    )
    @app_commands.autocomplete(day=lscc_day_autocomplete)
    @log_cmd
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def ask_drivers(self, interaction: discord.Interaction, day: str, message: str) -> None:
        """Pings the driver role with a custom message.

        Args:
            interaction: The Discord interaction.
            day: The day to ask for (e.g., 'Friday', 'Sunday').
            message: The custom message to send.
        """
        if not await cmd_is_allowed(
            interaction,
            interaction.channel_id,
            BOT_TESTING_CHANNELS | {ChannelIds.SERVING__DRIVER_CHAT_WOOOOO},
        ):
            return

        # Send the message and allow role mentions
        await interaction.response.send_message(
            self.driver_service.format_message(message),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        # Fetch the original response
        sent_message = await interaction.original_response()

        for emoji in self.driver_service.get_emojis(DaysOfWeek(day)):
            await sent_message.add_reaction(emoji)

        # Invalidate and warm the driver message ID cache
        event = DAY_TO_EVENT.get(day.lower())
        if event:
            await warm_ask_drivers_message_cache(self.bot, event)


async def setup(bot: commands.Bot):
    """Sets up the AskDrivers cog."""
    service = DriverService()
    await bot.add_cog(AskDrivers(bot, driver_service=service))
