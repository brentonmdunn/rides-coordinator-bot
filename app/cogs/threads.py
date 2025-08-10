"""cogs/threads.py"""

import asyncio

import discord
from discord.ext import commands
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.enums import FeatureFlagNames
from app.core.logger import logger
from app.core.models import EventThreads
from app.utils.checks import feature_flag_enabled


class Threads(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_thread(self, interaction: discord.Interaction) -> bool:
        """Helper to check if the interaction is in a thread."""
        return isinstance(interaction.channel, discord.Thread)

    @discord.app_commands.command(
        name="end-event-thread",
        description="Stops adding everyone who reacts.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def end_event_thread(self, interaction: discord.Interaction) -> None:
        if not self._is_thread(interaction):
            await interaction.response.send(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return
        thread = interaction.channel
        # The starter message ID is the same as the thread ID.
        starter_message_id = str(thread.id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(EventThreads).filter_by(message_id=starter_message_id)
            )
            message_to_delete = result.scalar_one_or_none()
            if message_to_delete:
                await session.delete(message_to_delete)
                await session.commit()
                await interaction.response.send_message(
                    "Event thread has ended. New reactions will not be added to the thread."
                )
            else:
                await interaction.response.send_message(
                    "No active event thread found.", ephemeral=True
                )

    @discord.app_commands.command(
        name="create-event-thread",
        description="Must be run in thread. Automatically adds anyone new who reacts.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def create_event_thread(self, interaction: discord.Interaction) -> None:
        """Automatically adds anyone new who reacts"""

        await interaction.response.defer(ephemeral=False, thinking=True)

        if not self._is_thread(interaction):
            await interaction.followup.send(
                "This command can only be used inside a thread.", ephemeral=True
            )
            return

        thread = interaction.channel
        # The starter message ID is the same as the thread ID.
        starter_message_id = str(thread.id)

        async with AsyncSessionLocal() as session:
            existing_thread = await session.get(EventThreads, starter_message_id)
            if existing_thread:
                await interaction.followup.send(
                    "Event thread has already been created.", ephemeral=True
                )
                return

        await interaction.followup.send(
            "Event thread has been created. Anyone who reacts to the original message will " \
            "automatically be added to this thread."
        )

        await self._bulk_add_reacts_to_thread(interaction)

        async with AsyncSessionLocal() as session:
            new_thread = EventThreads(message_id=starter_message_id)
            session.add(new_thread)
            await session.commit()

        await interaction.followup.send(
            "NOTE: This feature has a feature flag. If it is not "
            "properly working, use `/list-feature-flags` to check the status of "
            "`event_threads`",
            ephemeral=True,
        )

    @discord.app_commands.command(
        name="add-reacts-to-thread",
        description="Must be run in thread. Adds everyone who reacted to parent message to thread.",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def add_reacts_to_thread(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self._bulk_add_reacts_to_thread(interaction)

    async def _bulk_add_reacts_to_thread(self, interaction):
        thread = interaction.channel
        starter_message = None

        # The thread's ID is the same as the starter message's ID.
        try:
            # We must use fetch_message to ensure we get the message object
            # and its reactions, as it might not be in the bot's cache.
            starter_message = await thread.parent.fetch_message(thread.id)
        except discord.NotFound:
            await interaction.followup.send(
                "Could not find the message that started this thread. Has it been deleted?"
            )
            return
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to read the history of this "
                "channel to find the first message."
            )
            return

        if not starter_message.reactions:
            await interaction.followup.send("The first message has no reactions.")
            return

        reactors = set()
        for reaction in starter_message.reactions:
            # reaction.users() is an async iterator
            async for user in reaction.users():
                if not user.bot:
                    reactors.add(user)

        if not reactors:
            await interaction.followup.send("No users have reacted to the starter message yet.")
            return

        added_users = []
        failed_users = []

        # Fetch existing thread members to avoid adding them again.
        thread_members = await thread.fetch_members()
        thread_member_ids = {member.id for member in thread_members}

        for user in reactors:
            logger.info(f"{user=}")
            # Skip bots and users already in the thread.
            if user.bot or user.id in thread_member_ids:
                continue

            try:
                await thread.add_user(user)
                added_users.append(user.mention)
                # Small sleep to avoid hitting Discord's rate limits.
                await asyncio.sleep(0.25)
            except discord.Forbidden:
                # The bot doesn't have the necessary permissions.
                await interaction.followup.send(
                    "I lack the `Manage Threads` permission to add users to this private thread."
                )
                return
            except Exception as e:
                # Log any other unexpected errors.
                print(f"Failed to add {user.name}: {e}")
                failed_users.append(user.name)

        response_message = ""
        if added_users:
            response_message += f"✅ Successfully added {len(added_users)} users:\n" + ", ".join(
                added_users
            )
        if failed_users:
            if added_users:
                response_message += "\n"
            response_message += f"❌ Failed to add {len(failed_users)} users: " + ", ".join(
                failed_users
            )

        if not response_message:
            response_message = "All users who reacted are already in the thread."

        # Send the final message as a followup.
        await interaction.followup.send(response_message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Threads(bot))
