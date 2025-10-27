import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.jobs.ask_rides import (
    run_ask_rides_fri,
    run_ask_rides_header,
    run_ask_rides_sun,
)
from app.utils.checks import feature_flag_enabled


class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="test",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def test(self, interaction: discord.Interaction):
        await run_ask_rides_header(self.bot, interaction.channel_id)
        await run_ask_rides_fri(self.bot, interaction.channel_id)
        # await run_ask_rides_sun_class(self.bot, interaction.channel_id)
        await run_ask_rides_sun(self.bot, interaction.channel_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
