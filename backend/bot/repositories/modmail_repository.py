"""Repository for modmail channel data access."""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import ModmailChannels

logger = logging.getLogger(__name__)


class ModmailRepository:
    """Handles database operations for ModmailChannels."""

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: str) -> ModmailChannels | None:
        """
        Fetch an open modmail channel for a given user.

        Args:
            session: The database session.
            user_id: The Discord user ID.

        Returns:
            The ModmailChannels row if one exists and is not closed, otherwise None.
        """
        result = await session.execute(
            select(ModmailChannels)
            .where(ModmailChannels.user_id == user_id)
            .where(ModmailChannels.closed_at.is_(None)),
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_channel_id(
        session: AsyncSession,
        channel_id: str,
    ) -> ModmailChannels | None:
        """
        Fetch a modmail channel by its Discord channel ID.

        Args:
            session: The database session.
            channel_id: The Discord channel ID.

        Returns:
            The ModmailChannels row if found, otherwise None.
        """
        result = await session.execute(
            select(ModmailChannels).where(ModmailChannels.channel_id == channel_id),
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: str,
        channel_id: str,
        username: str | None,
    ) -> ModmailChannels:
        """
        Insert a new modmail channel mapping.

        Args:
            session: The database session.
            user_id: The Discord user ID.
            channel_id: The Discord channel ID.
            username: The Discord username (for display in logs).

        Returns:
            The newly created ModmailChannels row.
        """
        row = ModmailChannels(user_id=user_id, channel_id=channel_id, username=username)
        session.add(row)
        return row

    @staticmethod
    async def mark_closed(session: AsyncSession, row: ModmailChannels) -> None:
        """
        Mark a modmail channel row as closed.

        Args:
            session: The database session.
            row: The ModmailChannels row to close.
        """
        row.closed_at = datetime.now(UTC).replace(tzinfo=None)
