"""Cog for grouping rides."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.enums import FeatureFlagNames
from bot.core.logger import log_cmd
from bot.services.group_rides_service import GroupRidesService
from bot.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from bot.utils.checks import feature_flag_enabled


class GroupRides(commands.Cog):
    """Cog for handling group rides logic."""

    def __init__(self, bot: commands.Bot):
        """Initialize the GroupRides cog."""

        self.bot = bot
        self.service = GroupRidesService(bot)

    @app_commands.command(
        name="group-rides-friday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_friday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        custom_prompt: str | None = None,
        legacy_prompt: bool = False,
    ):
        """Groups riders with drivers for Friday fellowship.

        Args:
            interaction: The Discord interaction.
            driver_capacity: A string representing driver capacities (e.g., "44444").
            custom_prompt: A custom prompt to use for the LLM.
            legacy_prompt: Whether to use the legacy prompt.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.group_rides(
            interaction,
            driver_capacity,
            day="friday",
            legacy_prompt=legacy_prompt,
            custom_prompt=custom_prompt,
        )

    @app_commands.command(
        name="group-rides-sunday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_sunday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        custom_prompt: str | None = None,
        legacy_prompt: bool = False,
    ):
        """Groups riders with drivers for Sunday service.

        Args:
            interaction: The Discord interaction.
            driver_capacity: A string representing driver capacities (e.g., "44444").
            legacy_prompt: Whether to use the legacy prompt.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.group_rides(
            interaction,
            driver_capacity,
            day="sunday",
            legacy_prompt=legacy_prompt,
            custom_prompt=custom_prompt,
        )

    @app_commands.command(
        name="group-rides-by-message-id",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_message_id(
        self,
        interaction: discord.Interaction,
        message_id: str,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        """Groups riders with drivers based on a specific message ID.

        Args:
            interaction: The Discord interaction.
            message_id: The ID of the message to fetch pickups from.
            driver_capacity: A string representing driver capacities (e.g., "44444").
            legacy_prompt: Whether to use the legacy prompt.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        try:
            message_id_int = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "Message ID must be an integer.", ephemeral=True
            )
            return

        await self.service.group_rides(
            interaction, driver_capacity, message_id=message_id_int, legacy_prompt=legacy_prompt
        )

    @app_commands.command(
        name="make-route",
        description="Makes route based on specified locations",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        locations="The locations to make a route for, separate each location with a space",
        leave_time="The leave time for the route",
    )
    @log_cmd
    async def make_route(
        self,
        interaction: discord.Interaction,
        locations: str,
        leave_time: str,
    ):
        """Makes route based on specified locations.

        Args:
            interaction: The Discord interaction.
            locations: The locations to make a route for.
            leave_time: The leave time for the route.
        """
        try:
            drive_formatted = self.service.make_route(locations, leave_time)
            await interaction.response.send_message(drive_formatted)
            await interaction.channel.send("```\n" + drive_formatted + "\n```")
        except ValueError as e:
            await interaction.response.send_message(str(e))


async def setup(bot: commands.Bot):
    """Sets up the GroupRides cog."""
    await bot.add_cog(GroupRides(bot))
