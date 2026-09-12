import discord
from discord import app_commands
from discord.ext import commands

from ridebot.jobs.ask_rides import (
    run_ask_rides_all,
)
from ridebot.services.ride_request_service import RideRequestService
from ridebot.views.pickup_info import PickupInfoView
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
        description="Post the pickup-info buttons in this channel (local only).",
    )
    @bot_enabled
    async def test_register(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Tap a button to test the pickup info form.", view=PickupInfoView()
        )

    @app_commands.command(
        name="test-new-rider",
        description="Simulate reacting as an unregistered rider (local only).",
    )
    @bot_enabled
    async def test_new_rider(self, interaction: discord.Interaction):
        """Run the real new-rider flow: create or reuse your channel and post the prompt."""
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Run this in a server, not a DM.", ephemeral=True
            )
            return

        # Creating a channel and pinning can take longer than the 3s interaction window.
        await interaction.response.defer(ephemeral=True)
        posted = await RideRequestService(self.bot).handle_new_rider_reaction(
            interaction.user, interaction.guild
        )
        await interaction.followup.send(
            "Posted the pickup-info prompt in your new-rides channel."
            if posted
            else (
                "Nothing posted. Either a prompt is already the newest message in your "
                "channel, or the new-rides category is missing."
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
