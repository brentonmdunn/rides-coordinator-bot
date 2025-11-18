# app/features/locations/locations_cog.py

import discord
from discord.ext import commands

from app.core.enums import ChannelIds, FeatureFlagNames
from app.core.logger import log_cmd
from app.services.locations_service import LocationsService
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled
from app.utils.constants import MAP_LINKS


class Locations(commands.Cog):
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
        await self.service.sync_locations()
        await interaction.response.send_message("Sync complete")

    @discord.app_commands.command(
        name="pickup-location",
        description="Pickup location for a person (name or Discord username).",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def pickup_location(self, interaction: discord.Interaction, name: str):
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
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.list_locations_wrapper(
            interaction, message_id=message_id, channel_id=channel_id
        )

    @discord.app_commands.command(
        name="map-links",
        description="Google Map links for pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def map_links(self, interaction: discord.Interaction, location: str | None):
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
    await bot.add_cog(Locations(bot))
