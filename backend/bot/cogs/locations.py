"""Cog for location-related commands."""

import discord
from discord.ext import commands

from bot.core.enums import ChannelIds, FeatureFlagNames
from bot.core.logger import log_cmd
from bot.services.locations_service import LocationsService
from bot.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from bot.utils.checks import feature_flag_enabled
from bot.utils.constants import MAP_LINKS


class Locations(commands.Cog):
    """Cog for managing user locations and pickups."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = LocationsService(bot)

    @discord.app_commands.command(
        name="sync-locations",
        description="Sync Google Sheets with database.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def sync_locations(self, interaction: discord.Interaction):
        """Syncs Google Sheets data with the database.

        Args:
            interaction: The Discord interaction.
        """
        await self.service.sync_locations()
        await interaction.response.send_message("Sync complete")

    @discord.app_commands.command(
        name="pickup-location",
        description="Pickup location for a person (name or Discord username).",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def pickup_location(self, interaction: discord.Interaction, name: str):
        """Gets the pickup location for a person.

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
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_pickups_sunday(self, interaction: discord.Interaction):
        """Lists pickups for Sunday service.

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(interaction, day="sunday", option="Sunday pickup")

    @discord.app_commands.command(
        name="list-dropoffs-sunday-back",
        description="List dropoffs after Sunday service no lunch.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_dropoffs_sunday_back(self, interaction: discord.Interaction):
        """Lists dropoffs after Sunday service (no lunch).

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, day="sunday", option="Sunday dropoff back"
        )

    @discord.app_commands.command(
        name="list-dropoffs-sunday-lunch",
        description="List dropoffs after Sunday service lunch.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_dropoffs_sunday_lunch(self, interaction: discord.Interaction):
        """Lists dropoffs after Sunday service (with lunch).

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, day="sunday", option="Sunday dropoff lunch"
        )

    @discord.app_commands.command(
        name="list-pickups-friday",
        description="List pickups for Friday fellowship.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_locations_friday(self, interaction: discord.Interaction):
        """Lists pickups for Friday fellowship.

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(interaction, day="friday")

    @discord.app_commands.command(
        name="list-pickups-by-message-id",
        description="List pickups using a specific message ID.",
    )
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        channel_id="Optional channel ID where the message is located",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def list_locations_unknown(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str | None = str(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS),
    ):
        """Lists pickups based on a specific message ID.

        Args:
            interaction: The Discord interaction.
            message_id: The message ID to fetch pickups from.
            channel_id: The channel ID where the message is located.
        """
        try:
            message_id_int = int(message_id)
            channel_id_int = int(channel_id) if channel_id else None
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
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def map_links(self, interaction: discord.Interaction, location: str | None):
        """Provides Google Maps links for pickup locations.

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
        for loc_name, map_url in MAP_LINKS.items():
            if search_term and search_term not in loc_name.lower():
                continue
            await interaction.channel.send(loc_name)
            await interaction.channel.send(f"([Google Maps]({map_url}))")


async def setup(bot: commands.Bot):
    """Sets up the Locations cog."""
    await bot.add_cog(Locations(bot))
