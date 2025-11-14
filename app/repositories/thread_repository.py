from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import EventThreads


class EventThreadRepository:
    """Handles database operations for EventThreads."""

    async def get_by_id(self, session: AsyncSession, thread_id: str) -> EventThreads | None:
        """Fetches an EventThread by its ID (which is the message_id)."""
        return await session.get(EventThreads, thread_id)

    async def get_by_message_id(
        self, session: AsyncSession, message_id: str
    ) -> EventThreads | None:
        """Fetches an EventThread by its message_id."""
        result = await session.execute(select(EventThreads).filter_by(message_id=message_id))
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, thread_id: str) -> EventThreads:
        """Creates and adds a new EventThread to the session."""
        new_thread = EventThreads(message_id=thread_id)
        session.add(new_thread)
        return new_thread

    async def delete(self, session: AsyncSession, event_thread: EventThreads) -> None:
        """Deletes an EventThread from the session."""
        await session.delete(event_thread)
