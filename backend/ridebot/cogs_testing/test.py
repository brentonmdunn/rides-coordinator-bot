import discord
from discord import app_commands
from discord.ext import commands

from ridebot.jobs.ask_rides import (
    run_ask_rides_all,
)
from ridebot.views.registration import RegistrationView
from shared.utils.checks import bot_enabled


class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="test",
    )
    @bot_enabled
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message("Complete")
        await run_ask_rides_all(self.bot, interaction.channel_id)

    @app_commands.command(
        name="test-register",
        description="Post the roster Register button in this channel (local only).",
    )
    @bot_enabled
    async def test_register(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Tap **Rides Form** to test the roster form.", view=RegistrationView()
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
