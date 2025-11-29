"""Service for event thread management."""

import asyncio

import discord

from app.core.database import AsyncSessionLocal
from app.core.logger import logger
from app.repositories.thread_repository import EventThreadRepository


# Custom exceptions to communicate outcomes to the cog layer
class EventThreadError(Exception):
    """Base exception for thread service errors."""


class EventThreadAlreadyExistsError(EventThreadError):
    """Raised when an event thread is already being tracked."""


class EventThreadNotFoundError(EventThreadError):
    """Raised when no active event thread is found for an operation."""


class StarterMessageError(EventThreadError):
    """Raised when the thread's starter message cannot be found or read."""


class ThreadService:
    """Manages the business logic for event threads."""

    def __init__(self, repository: EventThreadRepository):
        self.repository = repository

    @staticmethod
    def format_bulk_add_response(
        added_users: list[discord.Member],
        failed_users: list[str],
    ) -> str:
        """Formats the response message for a bulk-add operation.

        Args:
            added_users: List of users successfully added.
            failed_users: List of names of users who couldn't be added.

        Returns:
            A formatted string summarizing the operation results.
        """
        response_message = ""
        if added_users:
            mentions = [user.mention for user in added_users]
            response_message += f"✅ Successfully added {len(added_users)} users:\n" + ", ".join(
                mentions
            )
        if failed_users:
            if added_users:
                response_message += "\n"
            response_message += f"❌ Failed to add {len(failed_users)} users: " + ", ".join(
                failed_users
            )

        if not response_message:
            response_message = "All users who reacted are already in the thread."
        return response_message

    async def end_event_thread(self, thread_id: str) -> None:
        """Stops tracking an event thread.

        Args:
            thread_id: The ID of the thread to stop tracking.

        Raises:
            EventThreadNotFoundError: If no matching thread is found in the DB.
        """
        async with AsyncSessionLocal() as session:
            # Use get_by_message_id as the ID is the thread/message ID
            thread_to_delete = await self.repository.get_by_message_id(session, thread_id)

            if not thread_to_delete:
                raise EventThreadNotFoundError("No active event thread found.")

            await self.repository.delete(session, thread_to_delete)
            await session.commit()

    async def create_event_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """Creates and registers a new event thread, then bulk-adds reactors.

        Args:
            thread: The Discord thread object.

        Returns:
            A tuple containing a list of added members and a list of failed usernames.

        Raises:
            EventThreadAlreadyExistsError: If the thread is already tracked.
            StarterMessageError: If the starter message can't be found.
            discord.Forbidden: If bot permissions are missing.
        """
        thread_id = str(thread.id)
        async with AsyncSessionLocal() as session:
            existing_thread = await self.repository.get_by_id(session, thread_id)
            if existing_thread:
                raise EventThreadAlreadyExistsError("Event thread has already been created.")

        # Perform bulk add *before* committing to DB, as per original logic
        added, failed = await self.bulk_add_reactors_to_thread(thread)

        async with AsyncSessionLocal() as session:
            await self.repository.create(session, thread_id)
            await session.commit()

        return added, failed

    async def bulk_add_reactors_to_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """Adds all users who reacted to the thread's starter message.

        Args:
            thread: The Discord thread object.

        Returns:
            A tuple of (added_users_list, failed_users_list).

        Raises:
            StarterMessageError: If the starter message can't be found.
            discord.Forbidden: If bot permissions are missing.
        """
        try:
            starter_message = await thread.parent.fetch_message(thread.id)
        except discord.NotFound:
            raise StarterMessageError(  # noqa
                "Could not find the message that started this thread. Has it been deleted?"
            )
        except discord.Forbidden:
            raise StarterMessageError(  # noqa
                "I don't have permission to read the history of this "
                "channel to find the first message."
            )

        if not starter_message.reactions:
            return [], []  # No reactions, return empty lists

        reactors = set()
        for reaction in starter_message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    reactors.add(user)

        if not reactors:
            return [], []  # No users reacted

        added_users = []
        failed_users = []

        try:
            thread_members = await thread.fetch_members()
            thread_member_ids = {member.id for member in thread_members}
        except discord.Forbidden:
            # This can happen if the bot was removed from the thread
            # after creation but before this command is run.
            logger.warning(
                f"Failed to fetch members for thread {thread.id}. "
                "Proceeding, but may try to add existing members."
            )
            thread_member_ids = set()

        for user in reactors:
            if user.bot or user.id in thread_member_ids:
                continue

            try:
                await thread.add_user(user)
                added_users.append(user)
                await asyncio.sleep(0.25)  # Avoid rate limits
            except discord.Forbidden:
                # This is a critical failure, bot can't add anyone
                raise
            except Exception:
                logger.exception(f"Failed to add {user.name} to thread {thread.name}")
                failed_users.append(user.name)

        return added_users, failed_users

    async def add_reactor_to_thread(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild, user: discord.Member
    ) -> bool:
        """Add a user to an event thread when they react to the thread's starter message.

        This method checks if the reacted message is associated with an event thread.
        If so, it automatically adds the reacting user to that thread.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction occurred.
            user: The user who added the reaction.

        Returns:
            True if user was added to a thread, False otherwise.
        """
        async with AsyncSessionLocal() as session:
            # Check if this message is an event thread
            is_event = await self.repository.is_event_thread(session, str(payload.message_id))

            if not is_event:
                return False

            # Get the thread object
            thread = guild.get_thread(payload.message_id)
            if not thread:
                logger.error(f"Could not find thread with ID {payload.message_id}")
                return False

            # Check if user is already in the thread
            thread_member_ids = await self.repository.get_thread_members(thread)

            if user.id in thread_member_ids:
                return False  # User already in thread

            # Add the user to the thread
            return await self.repository.add_user_to_thread(thread, user)

    async def remove_reactor_from_thread(
        self,
        payload: discord.RawReactionActionEvent,
        guild: discord.Guild,
        bot,
    ) -> bool:
        """Remove a user from an event thread when they remove all their reactions.

        This method checks if the reacted message is associated with an event thread.
        If the user has no remaining reactions on the message, they are removed from
        the thread.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction was removed.
            bot: The Discord bot instance for fetching messages.

        Returns:
            True if user was removed from thread, False otherwise.
        """
        async with AsyncSessionLocal() as session:
            # Check if this message is an event thread
            is_event = await self.repository.is_event_thread(session, str(payload.message_id))

            if not is_event:
                return False

        # We need to fetch the full message to check for remaining reactions
        channel = bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            logger.error(f"Could not find message with ID {payload.message_id}")
            return False

        # Count the user's remaining reactions
        user_reactions = await self.repository.count_user_reactions(message, payload.user_id)

        # Only proceed to remove the user if they have no reactions left
        if user_reactions > 0:
            return False

        user = guild.get_member(payload.user_id)
        if not user or user.bot:
            logger.info(f"Ignoring bot reaction removal from {user.name if user else 'unknown'}")
            return False

        thread = guild.get_thread(payload.message_id)
        if not thread:
            logger.error(f"Could not find thread with ID {payload.message_id}")
            return False

        # Check if the user is a member of the thread before attempting to remove
        thread_member_ids = await self.repository.get_thread_members(thread)

        if user.id not in thread_member_ids:
            return False  # User not in thread

        # Remove the user from the thread
        return await self.repository.remove_user_from_thread(thread, user)
