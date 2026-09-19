import logging

import discord
from discord import app_commands
from discord.ext import commands

from ridebot.services.temp_driver_service import TempDriverService
from shared.utils.checks import bot_enabled

logger = logging.getLogger(__name__)


class TempDriversTestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="test-expire-temp-drivers",
        description="Run the temp-driver expiry sweep now, bypassing the feature flag (local only).",
    )
    @bot_enabled
    async def test_expire_temp_drivers(self, interaction: discord.Interaction):
        """Run TempDriverService.expire_due() directly and report the count."""
        await interaction.response.defer(ephemeral=True)
        count = await TempDriverService(self.bot).expire_due()
        await interaction.followup.send(f"Processed {count} expired grant(s).", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TempDriversTestCog(bot))
