"""Service for event thread management."""

import asyncio
import logging

import discord

from bot.core.database import AsyncSessionLocal
from bot.repositories.thread_repository import EventThreadRepository

logger = logging.getLogger(__name__)


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

    @staticmethod
    async def _get_thread_members(thread: discord.Thread) -> set[int]:
        """Get all member IDs in a thread."""
        try:
            thread_members = await thread.fetch_members()
            return {member.id for member in thread_members}
        except discord.Forbidden:
            logger.error(f"Missing permissions to fetch members for thread {thread.id}")
            return set()
        except Exception as e:
            logger.error(f"Failed to fetch thread members: {e}")
            return set()

    @staticmethod
    async def _add_user_to_thread(thread: discord.Thread, user: discord.Member) -> bool:
        """Add a user to a Discord thread."""
        try:
            await thread.add_user(user)
            logger.info(f"Added user {user.name} to thread {thread.name} on reaction.")
            return True
        except discord.Forbidden:
            logger.error(
                f"Failed to add user {user.name} to thread {thread.name} "
                "due to insufficient permissions."
            )
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while adding user to thread: {e}")
            return False

    @staticmethod
    async def _remove_user_from_thread(thread: discord.Thread, user: discord.Member) -> bool:
        """Remove a user from a Discord thread."""
        try:
            await thread.remove_user(user)
            logger.info(
                f"Removed user {user.name} from thread {thread.name} after reaction removal."
            )
            return True
        except discord.Forbidden:
            logger.error(
                f"Failed to remove user {user.name} from thread {thread.name} "
                "due to insufficient permissions."
            )
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while removing user from thread: {e}")
            return False

    @staticmethod
    async def _count_user_reactions(message: discord.Message, user_id: int) -> int:
        """Count how many reactions a user has on a message."""
        user_reactions = 0
        for reaction in message.reactions:
            async for user in reaction.users():
                if user.id == user_id:
                    user_reactions += 1
        return user_reactions

    async def end_event_thread(self, thread_id: str) -> None:
        """
        Stops tracking an event thread.

        Args:
            thread_id: The ID of the thread to stop tracking.

        Raises:
            EventThreadNotFoundError: If no matching thread is found in the DB.
        """
        async with AsyncSessionLocal() as session:
            thread_to_delete = await EventThreadRepository.get_by_message_id(session, thread_id)

            if not thread_to_delete:
                raise EventThreadNotFoundError("No active event thread found.")

            await EventThreadRepository.delete(session, thread_to_delete)
            await session.commit()
            logger.info(f"end_event_thread: ended event thread {thread_id}")

    async def create_event_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """
        Creates and registers a new event thread, then bulk-adds reactors.

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
        logger.info(f"create_event_thread: creating event thread for thread_id={thread_id}")
        async with AsyncSessionLocal() as session:
            existing_thread = await EventThreadRepository.get_by_id(session, thread_id)
            if existing_thread:
                raise EventThreadAlreadyExistsError("Event thread has already been created.")

        added, failed = await self.bulk_add_reactors_to_thread(thread)

        async with AsyncSessionLocal() as session:
            await EventThreadRepository.create(session, thread_id)
            await session.commit()

        logger.info(
            f"create_event_thread: completed - added {len(added)} users, "
            f"{len(failed)} failed for thread_id={thread_id}"
        )
        return added, failed

    async def bulk_add_reactors_to_thread(
        self, thread: discord.Thread
    ) -> tuple[list[discord.Member], list[str]]:
        """
        Adds all users who reacted to the thread's starter message.

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
            return [], []

        reactors = set()
        for reaction in starter_message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    reactors.add(user)

        if not reactors:
            return [], []

        added_users = []
        failed_users = []

        try:
            thread_members = await thread.fetch_members()
            thread_member_ids = {member.id for member in thread_members}
        except discord.Forbidden:
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
                await asyncio.sleep(0.25)
            except discord.Forbidden:
                raise
            except Exception:
                logger.exception(f"Failed to add {user.name} to thread {thread.name}")
                failed_users.append(user.name)

        return added_users, failed_users

    async def add_reactor_to_thread(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild, user: discord.Member
    ) -> bool:
        """
        Add a user to an event thread when they react to the thread's starter message.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction occurred.
            user: The user who added the reaction.

        Returns:
            True if user was added to a thread, False otherwise.
        """
        async with AsyncSessionLocal() as session:
            is_event = await EventThreadRepository.is_event_thread(session, str(payload.message_id))

            if not is_event:
                return False

            thread = guild.get_thread(payload.message_id)
            if not thread:
                logger.error(f"Could not find thread with ID {payload.message_id}")
                return False

            thread_member_ids = await self._get_thread_members(thread)

            if user.id in thread_member_ids:
                return False

            result = await self._add_user_to_thread(thread, user)
            if result:
                logger.info(
                    f"add_reactor_to_thread: added user={user.name} to thread={payload.message_id}"
                )
            return result

    async def remove_reactor_from_thread(
        self,
        payload: discord.RawReactionActionEvent,
        guild: discord.Guild,
        bot,
    ) -> bool:
        """
        Remove a user from an event thread when they remove all their reactions.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction was removed.
            bot: The Discord bot instance for fetching messages.

        Returns:
            True if user was removed from thread, False otherwise.
        """
        async with AsyncSessionLocal() as session:
            is_event = await EventThreadRepository.is_event_thread(session, str(payload.message_id))

            if not is_event:
                return False

        channel = bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return False

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            logger.error(f"Could not find message with ID {payload.message_id}")
            return False

        user_reactions = await self._count_user_reactions(message, payload.user_id)

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

        thread_member_ids = await self._get_thread_members(thread)

        if user.id not in thread_member_ids:
            return False

        result = await self._remove_user_from_thread(thread, user)
        if result:
            logger.info(
                f"remove_reactor_from_thread: removed user={user.name} "
                f"from thread={payload.message_id}"
            )
        return result
