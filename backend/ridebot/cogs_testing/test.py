import logging

import discord
from discord import app_commands
from discord.ext import commands

from ridebot.jobs.ask_rides import (
    build_ask_rides_message,
    run_ask_rides_all,
)
from ridebot.services.ride_request_service import RideRequestService
from ridebot.views.pickup_info import PickupInfoView
from shared.core.enums import AskRidesMessageType
from shared.utils.checks import bot_enabled

logger = logging.getLogger(__name__)


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

    @app_commands.command(
        name="test-ask-rides-other",
        description="Post an ask-rides embed with the Something else button here (local only).",
    )
    @bot_enabled
    async def test_ask_rides_other(
        self, interaction: discord.Interaction, message_type: AskRidesMessageType
    ):
        """Post a test ask-rides announcement; the "Something else" button follows its flag."""
        await interaction.response.defer(ephemeral=True)

        built = await build_ask_rides_message(message_type)
        if built is None:
            await interaction.followup.send(
                "That date is a wildcard date; nothing to post.", ephemeral=True
            )
            return
        embed, reactions, view = built

        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("This channel can't receive messages.", ephemeral=True)
            return

        sent = await channel.send(
            embed=embed, view=view if view is not None else discord.utils.MISSING
        )
        for emoji in reactions:
            try:
                await sent.add_reaction(emoji)
            except discord.HTTPException:
                logger.exception("Failed to add reaction %r to test message %s", emoji, sent.id)

        reply = "Posted."
        if view is None:
            reply += " Heads up: ask_rides_other_button is OFF, so no button was attached."
        await interaction.followup.send(reply, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
