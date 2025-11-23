import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.jobs.ask_rides import (
    run_ask_rides_all,
)
from app.utils.checks import feature_flag_enabled


class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="test",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message("Complete")
        await run_ask_rides_all(self.bot, interaction.channel_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
