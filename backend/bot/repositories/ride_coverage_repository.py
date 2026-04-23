"""Repository for ride coverage data access."""

import datetime
import logging

from sqlalchemy import delete, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import RideCoverage as RideCoverageModel

logger = logging.getLogger(__name__)


class RideCoverageRepository:
    """Handles database operations for ride coverage."""

    @staticmethod
    async def add_coverage_entries(session: AsyncSession, usernames: list[str], message_id: str):
        """
        Adds multiple ride coverage entries to the database.

        Args:
            session: The database session.
            usernames: A list of discord usernames to add.
            message_id: The message ID associated with the entries.
        """
        if not usernames:
            return

        try:
            now = datetime.datetime.now()
            entries = [
                RideCoverageModel(
                    discord_username=username, datetime_detected=now, message_id=message_id
                )
                for username in usernames
            ]
            session.add_all(entries)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    async def get_coverage_status(
        session: AsyncSession, discord_username: str, hours: int = 24
    ) -> bool:
        """
        Checks if a ride coverage entry exists for the user within the last X hours.

        Args:
            session: The database session.
            discord_username: The discord username to check.
            hours: Time window in hours.

        Returns:
            bool: True if an entry exists, False otherwise.
        """
        try:
            since = datetime.datetime.now() - datetime.timedelta(hours=hours)
            stmt = select(RideCoverageModel).where(
                RideCoverageModel.discord_username == discord_username,
                RideCoverageModel.datetime_detected >= since,
            )
            result = await session.execute(stmt)
            return result.scalars().first() is not None
        except Exception:
            logger.exception("Failed to check coverage status for %s", discord_username)
            return False

    @staticmethod
    async def get_bulk_coverage_status(
        session: AsyncSession, discord_usernames: list[str], hours: int = 24
    ) -> set[str]:
        """
        Checks which of the given users have a ride coverage entry within the last X hours.

        Args:
            session: The database session.
            discord_usernames: List of discord usernames to check.
            hours: Time window in hours.

        Returns:
            set[str]: A set of usernames that have ride coverage entries.
        """
        if not discord_usernames:
            return set()

        try:
            since = datetime.datetime.now() - datetime.timedelta(hours=hours)
            stmt = select(RideCoverageModel.discord_username).where(
                RideCoverageModel.discord_username.in_(discord_usernames),
                RideCoverageModel.datetime_detected >= since,
            )
            result = await session.execute(stmt)
            return set(result.scalars().all())
        except Exception:
            logger.exception("Failed to check bulk coverage status")
            return set()

    @staticmethod
    async def delete_coverage_entries(session: AsyncSession, usernames: list[str], message_id: str):
        """
        Deletes ride coverage entries for the given usernames and message_id.

        Args:
            session: The database session.
            usernames: List of discord usernames to delete.
            message_id: The message ID associated with the entries.
        """
        if not usernames:
            return

        try:
            stmt = delete(RideCoverageModel).where(
                RideCoverageModel.discord_username.in_(usernames),
                RideCoverageModel.message_id == str(message_id),
            )
            await session.execute(stmt)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    async def delete_all_entries_by_message(session: AsyncSession, message_id: str) -> int:
        """
        Deletes all ride coverage entries for the given message_id.

        Args:
            session: The database session.
            message_id: The message ID associated with the entries.

        Returns:
            int: Number of entries deleted.
        """
        try:
            stmt = delete(RideCoverageModel).where(RideCoverageModel.message_id == str(message_id))
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    async def get_unique_message_ids(session: AsyncSession, since: datetime.datetime) -> set[str]:
        """
        Gets all unique message IDs from entries since the given datetime.

        Args:
            session: The database session.
            since: Start datetime to filter entries.

        Returns:
            set[str]: Set of unique message IDs.
        """
        try:
            stmt = select(distinct(RideCoverageModel.message_id)).where(
                RideCoverageModel.datetime_detected >= since
            )
            result = await session.execute(stmt)
            return set(result.scalars().all())
        except Exception:
            logger.exception("Failed to fetch unique message IDs")
            return set()

    @staticmethod
    async def has_coverage_entries(session: AsyncSession, since: datetime.datetime) -> bool:
        """
        Checks if any ride coverage entries exist since the given datetime.

        Args:
            session: The database session.
            since: Start datetime to check for entries.

        Returns:
            bool: True if any entries exist, False otherwise.
        """
        try:
            stmt = (
                select(RideCoverageModel)
                .where(RideCoverageModel.datetime_detected >= since)
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalars().first() is not None
        except Exception:
            logger.exception("Failed to check coverage entries")
            return False
