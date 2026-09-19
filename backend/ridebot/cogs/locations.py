"""Cog for location-related commands."""

import discord
from discord.ext import commands

from ridebot.services.locations_service import LocationsService
from ridebot.services.pickup_locations_service import PickupLocationsService
from ridebot.services.pickup_summary_service import PickupSummaryService
from ridebot.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from shared.core.enums import ChannelIds, JobName, PickupSummarySlot, RideOption
from shared.core.logger import log_cmd
from shared.utils.checks import bot_enabled


class Locations(commands.Cog):
    """Cog for managing user locations and pickups."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Locations cog."""
        self.bot = bot
        self.service = LocationsService(bot)

    @discord.app_commands.command(
        name="pickup-location",
        description="Pickup location for a person (name or Discord username).",
    )
    @bot_enabled
    @log_cmd
    async def pickup_location(self, interaction: discord.Interaction, name: str):
        """
        Gets the pickup location for a person.

        Args:
            interaction: The Discord interaction.
            name: The name or Discord username to look up.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        result = await self.service.pickup_location(name)
        await interaction.response.send_message(result)

    @discord.app_commands.command(
        name="list-pickups-sunday",
        description="List pickups for Sunday service.",
    )
    @bot_enabled
    @log_cmd
    async def list_pickups_sunday(self, interaction: discord.Interaction):
        """
        Lists pickups for Sunday service.

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, day=JobName.SUNDAY, option=RideOption.SUNDAY_PICKUP
        )

    @discord.app_commands.command(
        name="list-dropoffs-sunday-back",
        description="List dropoffs after Sunday service no lunch.",
    )
    @bot_enabled
    @log_cmd
    async def list_dropoffs_sunday_back(self, interaction: discord.Interaction):
        """
        Lists dropoffs after Sunday service (no lunch).

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, day=JobName.SUNDAY, option=RideOption.SUNDAY_DROPOFF_BACK
        )

    @discord.app_commands.command(
        name="list-dropoffs-sunday-lunch",
        description="List dropoffs after Sunday service lunch.",
    )
    @bot_enabled
    @log_cmd
    async def list_dropoffs_sunday_lunch(self, interaction: discord.Interaction):
        """
        Lists dropoffs after Sunday service (with lunch).

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, day=JobName.SUNDAY, option=RideOption.SUNDAY_DROPOFF_LUNCH
        )

    @discord.app_commands.command(
        name="list-pickups-friday",
        description="List pickups for Friday fellowship.",
    )
    @bot_enabled
    @log_cmd
    async def list_locations_friday(self, interaction: discord.Interaction):
        """
        Lists pickups for Friday fellowship.

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(interaction, day=JobName.FRIDAY)

    @discord.app_commands.command(
        name="send-pickups-summary",
        description="Post the scheduled pickup summary (with dashboard link) in this channel.",
    )
    @bot_enabled
    @log_cmd
    async def send_pickups_summary(self, interaction: discord.Interaction, day: PickupSummarySlot):
        """
        Posts the same message the scheduled pickup-summary job sends, in the current channel.

        Ignores the Site Settings on/off toggle, but still skips when there's nothing to post.

        Args:
            interaction: The Discord interaction.
            day: Which summary to send (friday or sunday).
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "This channel can't receive messages.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        sent = await PickupSummaryService(self.bot).send_summary(
            day, channel_id=interaction.channel_id, respect_toggle=False
        )
        await interaction.followup.send(
            "Sent."
            if sent
            else "Nothing sent: no ask-rides message went out this week, the ask-rides job is "
            "paused, or (Friday only) it's Wednesday-fellowship season.",
            ephemeral=True,
        )

    @discord.app_commands.command(
        name="list-pickups-by-message-id",
        description="List pickups using a specific message ID.",
    )
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        channel_id="Optional channel ID where the message is located",
    )
    @bot_enabled
    @log_cmd
    async def list_locations_unknown(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str | None = str(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS),
    ):
        """
        Lists pickups based on a specific message ID.

        Args:
            interaction: The Discord interaction.
            message_id: The message ID to fetch pickups from.
            channel_id: The channel ID where the message is located.
        """
        try:
            message_id_int = int(message_id)
            channel_id_int = (
                int(channel_id) if channel_id else int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )
        except ValueError:
            await interaction.response.send_message(
                "Message ID and Channel ID must be integers.", ephemeral=True
            )
            return

        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, message_id=message_id_int, channel_id=channel_id_int
        )

    @discord.app_commands.command(
        name="map-links",
        description="Google Map links for pickups",
    )
    @bot_enabled
    @log_cmd
    async def map_links(self, interaction: discord.Interaction, location: str | None):
        """
        Provides Google Maps links for pickup locations.

        Args:
            interaction: The Discord interaction.
            location: Optional specific location to filter by.
        """
        search_term = location.lower() if location else None
        header = (
            f"**{location}**"
            if location
            else "**All locations** (slight rate limit warning so all don't send at once)"
        )
        await interaction.response.send_message(header)
        if not isinstance(interaction.channel, discord.TextChannel):
            return
        routing = await PickupLocationsService.get_routing_context()
        for name, map_url in routing.map_links().items():
            if search_term and search_term not in name.lower():
                continue
            await interaction.channel.send(name)
            await interaction.channel.send(f"([Google Maps]({map_url}))")


async def setup(bot: commands.Bot):
    """Sets up the Locations cog."""
    await bot.add_cog(Locations(bot))
