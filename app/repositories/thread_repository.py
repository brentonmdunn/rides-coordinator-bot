"""Repository for event thread data access."""

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.models import EventThreads


class EventThreadRepository:
    """Handles database operations for EventThreads."""

    async def get_by_id(self, session: AsyncSession, thread_id: str) -> EventThreads | None:
        """Fetches an EventThread by its ID (which is the message_id).

        Args:
            session: The database session.
            thread_id: The ID of the thread.

        Returns:
            The EventThreads object if found, otherwise None.
        """
        return await session.get(EventThreads, thread_id)

    async def get_by_message_id(
        self, session: AsyncSession, message_id: str
    ) -> EventThreads | None:
        """Fetches an EventThread by its message_id.

        Args:
            session: The database session.
            message_id: The message ID.

        Returns:
            The EventThreads object if found, otherwise None.
        """
        result = await session.execute(select(EventThreads).filter_by(message_id=message_id))
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, thread_id: str) -> EventThreads:
        """Creates and adds a new EventThread to the session.

        Args:
            session: The database session.
            thread_id: The ID of the thread.

        Returns:
            The created EventThreads object.
        """
        new_thread = EventThreads(message_id=thread_id)
        session.add(new_thread)
        return new_thread

    async def delete(self, session: AsyncSession, event_thread: EventThreads) -> None:
        """Deletes an EventThread from the session.

        Args:
            session: The database session.
            event_thread: The EventThreads object to delete.
        """
        await session.delete(event_thread)

    async def is_event_thread(self, session: AsyncSession, message_id: str) -> bool:
        """Check if a message ID corresponds to an event thread.

        Args:
            session: The database session.
            message_id: The message ID to check.

        Returns:
            True if the message is an event thread, False otherwise.
        """
        result = await self.get_by_message_id(session, message_id)
        return result is not None

    async def get_thread_members(self, thread: discord.Thread) -> set[int]:
        """Get all member IDs in a thread.

        Args:
            thread: The Discord thread.

        Returns:
            A set of member IDs in the thread.
        """
        try:
            thread_members = await thread.fetch_members()
            return {member.id for member in thread_members}
        except discord.Forbidden:
            logger.error(f"Missing permissions to fetch members for thread {thread.id}")
            return set()
        except Exception as e:
            logger.error(f"Failed to fetch thread members: {e}")
            return set()

    async def add_user_to_thread(self, thread: discord.Thread, user: discord.Member) -> bool:
        """Add a user to a Discord thread.

        Args:
            thread: The Discord thread.
            user: The user to add.

        Returns:
            True if successful, False otherwise.
        """
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

    async def remove_user_from_thread(self, thread: discord.Thread, user: discord.Member) -> bool:
        """Remove a user from a Discord thread.

        Args:
            thread: The Discord thread.
            user: The user to remove.

        Returns:
            True if successful, False otherwise.
        """
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

    async def count_user_reactions(self, message: discord.Message, user_id: int) -> int:
        """Count how many reactions a user has on a message.

        Args:
            message: The Discord message.
            user_id: The ID of the user.

        Returns:
            The number of reactions the user has on the message.
        """
        user_reactions = 0
        for reaction in message.reactions:
            async for user in reaction.users():
                if user.id == user_id:
                    user_reactions += 1
        return user_reactions
