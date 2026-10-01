"""
Cog for manually running the new-rider registration prompt for a member.

Normally the new-rider flow fires from a reaction on the ride announcement
(``Reactions._new_rides_helper``). This command lets a ride coordinator run the
same flow by hand for a chosen member — e.g. when a reaction was dropped by a
transient Discord outage and never created the rider's channel.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ridebot.services.pickup_info_service import PickupInfoService
from ridebot.services.ride_request_service import RideRequestService
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_cmd
from shared.utils.checks import bot_enabled, is_ride_coordinator

logger = logging.getLogger(__name__)


class NewRider(commands.Cog):
    """Slash command for manually prompting a rider to register."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="prompt-new-rider",
        description="Create/reuse a rider's new-rides channel and post the registration prompt.",
    )
    @app_commands.describe(user="The member to prompt for pickup-info registration.")
    @is_ride_coordinator()
    @bot_enabled
    @log_cmd
    async def prompt_new_rider(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Run the real new-rider flow for a chosen member, if they aren't registered yet."""
        if interaction.guild is None:
            await interaction.response.send_message(
                "Run this in a server, not a DM.", ephemeral=True
            )
            return

        # Channel creation + history read can exceed Discord's 3s window.
        await interaction.response.defer(ephemeral=True)

        # Mirror _new_rides_helper: registered riders already have a location, so
        # there's nothing to prompt for.
        existing = await PickupInfoService.find_member(
            discord_user_id=user.id, discord_username=user.name
        )
        if existing is not None:
            where = existing.location or "no location set"
            await interaction.followup.send(
                f"{user.mention} is already registered ({where}); nothing posted.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        try:
            posted = await RideRequestService(self.bot).handle_new_rider_reaction(
                user, interaction.guild
            )
        except Exception:
            logger.exception("Failed to prompt new rider %s", user.name)
            await send_error_to_discord(f"**Error** prompting new rider `{user.name}`")
            await interaction.followup.send(
                f"Something went wrong prompting {user.mention}.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        await interaction.followup.send(
            f"Posted the pickup-info prompt in {user.mention}'s new-rides channel."
            if posted
            else (
                f"Nothing posted for {user.mention}. Either a prompt is already the newest "
                "message in their channel, or the new-rides category is missing."
            ),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def setup(bot: commands.Bot):
    """Set up the NewRider cog."""
    await bot.add_cog(NewRider(bot))
