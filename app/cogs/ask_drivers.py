"""cogs/ask_drivers.py"""

import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import (
    ChannelIds,
    DaysOfWeek,
    FeatureFlagNames,
    RoleIds,
)
from app.core.logger import log_cmd
from app.utils.channel_whitelist import (
    BOT_TESTING_CHANNELS,
    cmd_is_allowed,
)
from app.utils.checks import feature_flag_enabled
from app.utils.format_message import ping_role_with_message


class AskDrivers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def day_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        days = [DaysOfWeek.SUNDAY, DaysOfWeek.FRIDAY]
        return [
            app_commands.Choice(name=day, value=day)
            for day in days
            if current.lower() in day.lower()
        ]

    @discord.app_commands.command(
        name="ask-drivers",
        description="Pings drivers to see who is available.",
    )
    @app_commands.autocomplete(day=day_autocomplete)
    @log_cmd
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def ask_drivers(self, interaction: discord.Interaction, day: str, message: str) -> None:
        """Pings the driver role with a custom message."""
        if not await cmd_is_allowed(
            interaction,
            interaction.channel_id,
            BOT_TESTING_CHANNELS | {ChannelIds.SERVING__DRIVER_CHAT_WOOOOO},
        ):
            return

        message_to_send = ping_role_with_message(RoleIds.DRIVER, message)

        # Send the message and allow role mentions
        await interaction.response.send_message(
            message_to_send,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        # Fetch the original response
        sent_message = await interaction.original_response()

        if day == DaysOfWeek.SUNDAY:
            reactions = ["🍔", "🏠", "🔄", "❌", "➡️", "⬅️", "💩"]
        else:  # Friday
            reactions = ["👍", "❌", "➡️", "⬅️", "💩"]
        for emoji in reactions:
            await sent_message.add_reaction(emoji)


async def setup(bot: commands.Bot):
    await bot.add_cog(AskDrivers(bot))
