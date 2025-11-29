"""Cog for managing Discord threads."""

import discord
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.repositories.thread_repository import EventThreadRepository
from app.services.thread_service import (
    EventThreadAlreadyExistsError,
    EventThreadNotFoundError,
    StarterMessageError,
    ThreadService,
)
from app.utils.checks import feature_flag_enabled


class Threads(commands.Cog):
    """Cog for managing event-based threads."""

    def __init__(self, bot: commands.Bot, thread_service: ThreadService):
        self.bot = bot
        self.thread_service = thread_service

    def _is_thread(self, interaction: discord.Interaction) -> bool:
        """Helper to check if the interaction is in a thread.

        Args:
            interaction: The Discord interaction.

        Returns:
            True if the interaction channel is a thread, False otherwise.
        """
        return isinstance(interaction.channel, discord.Thread)


    @discord.app_commands.command(
        name="end-event-thread",
        description="Stops adding everyone who reacts.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def end_event_thread(self, interaction: discord.Interaction) -> None:
        """Stops adding everyone who reacts to the thread.

        Args:
            interaction: The Discord interaction.
        """
        if not self._is_thread(interaction):
            await interaction.response.send_message(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return

        thread_id = str(interaction.channel.id)

        try:
            await self.thread_service.end_event_thread(thread_id)
            await interaction.response.send_message(
                "Event thread has ended. New reactions will not be added to the thread."
            )
        except EventThreadNotFoundError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @discord.app_commands.command(
        name="create-event-thread",
        description="Must be run in thread. Automatically adds anyone new who reacts.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def create_event_thread(self, interaction: discord.Interaction) -> None:
        """Automatically adds anyone new who reacts to the parent message.

        Args:
            interaction: The Discord interaction.
        """
        await interaction.response.defer(ephemeral=False, thinking=True)

        if not self._is_thread(interaction):
            await interaction.followup.send(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return

        thread = interaction.channel

        try:
            added, failed = await self.thread_service.create_event_thread(thread)

            # Send the first success message
            await interaction.followup.send(
                "Event thread has been created. Anyone who reacts to the "
                "original message will automatically be added to this thread."
            )

            # Send the bulk add report
            response = self.thread_service.format_bulk_add_response(added, failed)
            if response != "All users who reacted are already in the thread.":
                await interaction.followup.send(response, ephemeral=True)

            # Send the feature flag note
            await interaction.followup.send(
                "NOTE: This feature has a feature flag. If it is not "
                "properly working, use `/list-feature-flags` to check "
                "the status of `event_threads`",
                ephemeral=True,
            )

        except EventThreadAlreadyExistsError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except StarterMessageError as e:
            await interaction.followup.send(str(e))
        except discord.Forbidden:
            await interaction.followup.send(
                "I lack the `Manage Threads` permission to add users to this private thread."
            )

    @discord.app_commands.command(
        name="add-reacts-to-thread",
        description="Must be run in thread. Adds everyone who reacted to parent message to thread.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def add_reacts_to_thread(self, interaction: discord.Interaction) -> None:
        """Adds everyone who reacted to the parent message to the thread.

        Args:
            interaction: The Discord interaction.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not self._is_thread(interaction):
            await interaction.followup.send(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return

        thread = interaction.channel

        try:
            added, failed = await self.thread_service.bulk_add_reactors_to_thread(thread)
            response = self.thread_service.format_bulk_add_response(added, failed)
            await interaction.followup.send(response, ephemeral=True)

        except StarterMessageError as e:
            await interaction.followup.send(str(e))
        except discord.Forbidden:
            await interaction.followup.send(
                "I lack the `Manage Threads` permission to add users to this private thread."
            )


async def setup(bot: commands.Bot):
    """Sets up the Threads cog."""
    # This is where Dependency Injection happens
    repo = EventThreadRepository()
    service = ThreadService(repository=repo)
    await bot.add_cog(Threads(bot, thread_service=service))
