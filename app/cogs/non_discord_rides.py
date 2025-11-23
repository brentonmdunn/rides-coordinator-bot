"""Cog for managing non-Discord rides."""

import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import (
    FeatureFlagNames,
)
from app.core.logger import log_cmd, logger
from app.services.non_discord_rides_service import DuplicateRideError, NonDiscordRidesService
from app.utils.autocomplete import location_autocomplete, lscc_day_autocomplete
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled


class NonDiscordRidesCog(commands.Cog):
    """Cog for handling pickups for users without Discord."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = NonDiscordRidesService()

    @app_commands.command(
        name="add-pickup",
        description="Add non-Discord user to list of pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=lscc_day_autocomplete)
    @app_commands.autocomplete(location=location_autocomplete)
    @log_cmd
    async def add_pickup(
        self, interaction: discord.Interaction, name: str, day: str, location: str
    ):
        """Adds a pickup for a non-Discord user.

        Args:
            interaction: The Discord interaction.
            name: The name of the person.
            day: The day of the pickup.
            location: The pickup location.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        try:
            await self.service.add_pickup(name, day, location)
            await interaction.response.send_message(
                f"Added {name} for pickup at {location} on {day}."
            )
        except DuplicateRideError:
            await interaction.response.send_message(
                f"Pickup for {name} on {day} already exists.", ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {e}")

    @app_commands.command(
        name="remove-pickup",
        description="Remove a non-Discord user from the list of pickups",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=lscc_day_autocomplete)
    @log_cmd
    async def remove_pickup(self, interaction: discord.Interaction, name: str, day: str):
        """Removes a non-Discord user's pickup entry.

        Args:
            interaction: The Discord interaction.
            name: The name of the person.
            day: The day of the pickup.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        try:
            success = await self.service.remove_pickup(name, day)

            if success:
                await interaction.response.send_message(
                    f"Successfully removed the pickup entry for **{name}** on **{day}**."
                )
            else:
                # If the entry does not exist
                await interaction.response.send_message(
                    f"Could not find a pickup entry for **{name}** on **{day}**.",
                    ephemeral=True,
                )

        except Exception:
            # Handle other potential errors
            logger.exception("An unexpected error occurred")
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.", ephemeral=True
            )

    @app_commands.command(
        name="list-added-pickups",
        description="Lists all added pickups for a specific day.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @app_commands.autocomplete(day=lscc_day_autocomplete)
    @log_cmd
    async def list_added_pickups(self, interaction: discord.Interaction, day: str):
        """Lists all non-Discord user pickups for a given day.

        Args:
            interaction: The Discord interaction.
            day: The day to list pickups for.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        try:
            pickups = await self.service.list_pickups(day)

            if pickups:
                # Format the list of pickups
                message = f"**Pickups for {day}:**\n"
                for pickup in pickups:
                    message += f"- {pickup.name} at {pickup.location}\n"

                await interaction.response.send_message(message)
            else:
                # If no pickups are found
                await interaction.response.send_message(
                    f"No pickups found for **{day}**.", ephemeral=True
                )

        except Exception:
            logger.exception("An error occurred while listing pickups:")
            await interaction.response.send_message(
                "An error occurred while trying to list the pickups. Please try again later.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    """Sets up the NonDiscordRidesCog."""
    await bot.add_cog(NonDiscordRidesCog(bot))
