"""Cog for event-related commands."""

import discord
from discord.ext import commands

# Your original imports
from bot.core.enums import FeatureFlagNames
from bot.core.logger import log_cmd, logger
from bot.repositories.events_repository import EventsRepository

# New imports for DI
from bot.services.events_service import EventsService
from bot.utils.checks import feature_flag_enabled, is_admin
from bot.utils.custom_exceptions import (
    ChannelNotFoundError,
    MessageNotFoundError,
    RoleNotFoundError,
    RoleServiceError,
)


class EventsCog(commands.Cog):
    """Cog for managing event-related tasks, such as role assignment based on reactions."""

    def __init__(self, bot: commands.Bot, events_service: EventsService):
        self.bot = bot
        self.events_service = events_service

    @discord.app_commands.command(
        name="assign-role-to-reacts",
        description="Assign a role to everyone who reacted to a specific message.",
    )
    @discord.app_commands.describe(
        message_id="The ID of the message to check reactions on.",
        channel_id="The ID of the channel the message is in.",
        role_name="Name of the role to assign.",
    )
    @log_cmd
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @is_admin()
    async def give_role(
        self,
        interaction: discord.Interaction,
        message_id: str,
        channel_id: str,
        role_name: str,
    ):
        """Assigns a role to everyone who reacted to a specific message.

        Args:
            interaction: The Discord interaction.
            message_id: The ID of the message to check reactions on.
            channel_id: The ID of the channel the message is in.
            role_name: The name of the role to assign.
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "This command must be used in a server.",
                ephemeral=True,
            )
            return

        # Acknowledge the command
        await interaction.response.defer(ephemeral=True)

        # --- Input Validation (Presentation Layer) ---
        try:
            msg_id_int = int(message_id)
            chan_id_int = int(channel_id)
        except ValueError:
            await interaction.followup.send(
                "Invalid message or channel ID. They must be numbers.",
                ephemeral=True,
            )
            return

        # --- Call Service Layer ---
        try:
            added_count = await self.events_service.assign_role_to_reactors(
                guild_id=interaction.guild.id,
                channel_id=chan_id_int,
                message_id=msg_id_int,
                role_name=role_name,
            )

            # --- Report Success (Presentation Layer) ---
            await interaction.followup.send(
                f"Successfully gave **{role_name}** role to **{added_count}** user(s).",
                ephemeral=False,  # Make success message public
            )

        # --- Handle Errors (Presentation Layer) ---
        except ChannelNotFoundError:
            await interaction.followup.send(
                "Could not find the specified text channel.", ephemeral=True
            )
        except MessageNotFoundError:
            await interaction.followup.send("Message not found.", ephemeral=True)
        except RoleNotFoundError:
            await interaction.followup.send("Role not found.", ephemeral=True)
        except RoleServiceError as e:
            # Catch other potential service errors
            logger.error(f"A service error occurred: {e}")
            await interaction.followup.send(
                "An error occurred while processing the command.", ephemeral=True
            )
        except Exception as e:
            # Catch any unexpected errors
            logger.error(f"An unexpected error occurred: {e}")
            await interaction.followup.send("An unexpected error occurred.", ephemeral=True)


async def setup(bot: commands.Bot):
    """Sets up the EventsCog.

    Performs dependency injection for the repository and service.
    """
    repository = EventsRepository(bot)
    service = EventsService(repository)
    await bot.add_cog(EventsCog(bot, service))
