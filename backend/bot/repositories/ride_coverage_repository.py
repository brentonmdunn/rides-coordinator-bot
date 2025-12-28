"""Repository for ride coverage data access."""

import datetime

from sqlalchemy import delete

from bot.core.database import AsyncSessionLocal
from bot.core.models import RideCoverage as RideCoverageModel


class RideCoverageRepository:
    """Handles database operations for ride coverage."""

    async def add_coverage_entries(self, usernames: list[str], message_id: str):
        """
        Adds multiple ride coverage entries to the database.

        Args:
            usernames: A list of discord usernames to add.
        """
        if not usernames:
            return

        async with AsyncSessionLocal() as session:
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

    async def get_coverage_status(self, discord_username: str, hours: int = 24) -> bool:
        """
        Checks if a ride coverage entry exists for the user within the last X hours.

        Args:
            discord_username: The discord username to check.
            hours: Time window in hours.

        Returns:
            bool: True if an entry exists, False otherwise.
        """
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            try:
                since = datetime.datetime.now() - datetime.timedelta(hours=hours)
                stmt = select(RideCoverageModel).where(
                    RideCoverageModel.discord_username == discord_username,
                    RideCoverageModel.datetime_detected >= since,
                )
                result = await session.execute(stmt)
                return result.scalars().first() is not None
            except Exception:
                return False

    async def get_bulk_coverage_status(
        self, discord_usernames: list[str], hours: int = 24
    ) -> set[str]:
        """
        Checks which of the given users have a ride coverage entry within the last X hours.

        Args:
            discord_usernames: List of discord usernames to check.
            hours: Time window in hours.

        Returns:
            set[str]: A set of usernames that have ride coverage entries.
        """
        from sqlalchemy import select

        if not discord_usernames:
            return set()

        async with AsyncSessionLocal() as session:
            try:
                since = datetime.datetime.now() - datetime.timedelta(hours=hours)
                stmt = select(RideCoverageModel.discord_username).where(
                    RideCoverageModel.discord_username.in_(discord_usernames),
                    RideCoverageModel.datetime_detected >= since,
                )
                result = await session.execute(stmt)
                return set(result.scalars().all())
            except Exception:
                return set()

    async def delete_coverage_entries(self, usernames: list[str], message_id: str):
        """
        Deletes ride coverage entries for the given usernames and message_id.

        Args:
            usernames: List of discord usernames to delete.
            message_id: The message ID associated with the entries.
        """
        if not usernames:
            return

        async with AsyncSessionLocal() as session:
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

    async def delete_all_entries_by_message(self, message_id: str) -> int:
        """
        Deletes all ride coverage entries for the given message_id.

        Args:
            message_id: The message ID associated with the entries.

        Returns:
            int: Number of entries deleted.
        """
        async with AsyncSessionLocal() as session:
            try:
                stmt = delete(RideCoverageModel).where(
                    RideCoverageModel.message_id == str(message_id)
                )
                result = await session.execute(stmt)
                await session.commit()
                return result.rowcount
            except Exception:
                await session.rollback()
                raise

    async def get_unique_message_ids(self, since: datetime.datetime) -> set[str]:
        """
        Gets all unique message IDs from entries since the given datetime.

        Args:
            since: Start datetime to filter entries.

        Returns:
            set[str]: Set of unique message IDs.
        """
        from sqlalchemy import distinct, select

        async with AsyncSessionLocal() as session:
            try:
                stmt = select(distinct(RideCoverageModel.message_id)).where(
                    RideCoverageModel.datetime_detected >= since
                )
                result = await session.execute(stmt)
                return set(result.scalars().all())
            except Exception:
                return set()

    async def has_coverage_entries(self, since: datetime.datetime) -> bool:
        """
        Checks if any ride coverage entries exist since the given datetime.

        Args:
            since: Start datetime to check for entries.

        Returns:
            bool: True if any entries exist, False otherwise.
        """
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            try:
                stmt = (
                    select(RideCoverageModel)
                    .where(RideCoverageModel.datetime_detected >= since)
                    .limit(1)
                )
                result = await session.execute(stmt)
                return result.scalars().first() is not None
            except Exception:
                return False
