"""Repository for event thread data access."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import EventThreads

logger = logging.getLogger(__name__)


class EventThreadRepository:
    """Handles database operations for EventThreads."""

    @staticmethod
    async def get_by_id(session: AsyncSession, thread_id: str) -> EventThreads | None:
        """
        Fetches an EventThread by its ID (which is the message_id).

        Args:
            session: The database session.
            thread_id: The ID of the thread.

        Returns:
            The EventThreads object if found, otherwise None.
        """
        return await session.get(EventThreads, thread_id)

    @staticmethod
    async def get_by_message_id(session: AsyncSession, message_id: str) -> EventThreads | None:
        """
        Fetches an EventThread by its message_id.

        Args:
            session: The database session.
            message_id: The message ID.

        Returns:
            The EventThreads object if found, otherwise None.
        """
        result = await session.execute(select(EventThreads).filter_by(message_id=message_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def create(session: AsyncSession, thread_id: str) -> EventThreads:
        """
        Creates and adds a new EventThread to the session.

        Args:
            session: The database session.
            thread_id: The ID of the thread.

        Returns:
            The created EventThreads object.
        """
        new_thread = EventThreads(message_id=thread_id)
        session.add(new_thread)
        return new_thread

    @staticmethod
    async def delete(session: AsyncSession, event_thread: EventThreads) -> None:
        """
        Deletes an EventThread from the session.

        Args:
            session: The database session.
            event_thread: The EventThreads object to delete.
        """
        await session.delete(event_thread)

    @staticmethod
    async def is_event_thread(session: AsyncSession, message_id: str) -> bool:
        """
        Check if a message ID corresponds to an event thread.

        Args:
            session: The database session.
            message_id: The message ID to check.

        Returns:
            True if the message is an event thread, False otherwise.
        """
        result = await EventThreadRepository.get_by_message_id(session, message_id)
        return result is not None
