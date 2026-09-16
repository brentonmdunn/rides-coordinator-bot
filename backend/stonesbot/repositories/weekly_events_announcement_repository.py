"""Repository for weekly events announcement data access."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.models import WeeklyEventsAnnouncement

logger = logging.getLogger(__name__)


class WeeklyEventsAnnouncementRepository:
    """Handles database operations for WeeklyEventsAnnouncement."""

    @staticmethod
    async def get_latest(session: AsyncSession) -> WeeklyEventsAnnouncement | None:
        """
        Fetch the most recently posted announcement.

        Args:
            session: The database session.

        Returns:
            The newest WeeklyEventsAnnouncement, or None if none have been posted.
        """
        result = await session.execute(
            select(WeeklyEventsAnnouncement).order_by(WeeklyEventsAnnouncement.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(session: AsyncSession) -> list[WeeklyEventsAnnouncement]:
        """
        Fetch every recorded announcement, oldest first.

        Args:
            session: The database session.

        Returns:
            A list of WeeklyEventsAnnouncement rows.
        """
        result = await session.execute(
            select(WeeklyEventsAnnouncement).order_by(WeeklyEventsAnnouncement.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create(
        session: AsyncSession,
        message_id: str,
        channel_id: str,
        week_start,
        week_end,
    ) -> WeeklyEventsAnnouncement:
        """
        Record a newly posted announcement.

        Args:
            session: The database session.
            message_id: The posted message's id.
            channel_id: The channel the message was posted in.
            week_start: First date covered by the announcement.
            week_end: Last date covered by the announcement.

        Returns:
            The created WeeklyEventsAnnouncement object.
        """
        announcement = WeeklyEventsAnnouncement(
            message_id=message_id,
            channel_id=channel_id,
            week_start=week_start,
            week_end=week_end,
        )
        session.add(announcement)
        return announcement

    @staticmethod
    async def delete(session: AsyncSession, announcement: WeeklyEventsAnnouncement) -> None:
        """
        Delete an announcement row.

        Args:
            session: The database session.
            announcement: The row to delete.
        """
        await session.delete(announcement)
