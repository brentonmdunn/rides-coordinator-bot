"""Repository for modmail channel data access."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import ModmailChannels

logger = logging.getLogger(__name__)


class ModmailRepository:
    """Handles database operations for ModmailChannels."""

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: str) -> ModmailChannels | None:
        """
        Fetch the modmail channel mapping for a given user.

        Args:
            session: The database session.
            user_id: The Discord user ID.

        Returns:
            The ModmailChannels row if one exists, otherwise None.
        """
        return await session.get(ModmailChannels, user_id)

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
    async def delete(session: AsyncSession, row: ModmailChannels) -> None:
        """
        Remove a modmail channel mapping.

        Args:
            session: The database session.
            row: The ModmailChannels row to delete.
        """
        await session.delete(row)
