"""Data access layer for temporary Driver role grants."""

from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.models import TempDriverGrant


class TempDriverGrantsRepository:
    """Handles database operations for temporary Driver role grants."""

    @staticmethod
    async def upsert(
        session: AsyncSession,
        discord_user_id: str,
        discord_username: str,
        expires_at: datetime,
        granted_by: str,
    ) -> None:
        """Insert or update the grant row for a Discord user. Does not commit."""
        naive_expires_at = expires_at.replace(tzinfo=None)
        stmt = insert(TempDriverGrant).values(
            discord_user_id=discord_user_id,
            discord_username=discord_username,
            expires_at=naive_expires_at,
            granted_by=granted_by,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[TempDriverGrant.discord_user_id],
            set_={
                "discord_username": discord_username,
                "expires_at": naive_expires_at,
                "granted_by": granted_by,
            },
        )
        await session.execute(stmt)

    @staticmethod
    async def get(session: AsyncSession, discord_user_id: str) -> TempDriverGrant | None:
        """Return the grant row for a Discord user, or None if there isn't one."""
        stmt = select(TempDriverGrant).where(TempDriverGrant.discord_user_id == discord_user_id)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @staticmethod
    async def list_all(session: AsyncSession) -> list[TempDriverGrant]:
        """Return every grant row, ordered by expiry ascending."""
        stmt = select(TempDriverGrant).order_by(TempDriverGrant.expires_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_expired(session: AsyncSession, now: datetime) -> list[TempDriverGrant]:
        """Return every grant row whose expiry is at or before `now`."""
        naive_now = now.replace(tzinfo=None)
        stmt = select(TempDriverGrant).where(TempDriverGrant.expires_at <= naive_now)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, discord_user_id: str) -> bool:
        """
        Delete the grant row for a Discord user. Does not commit.

        Returns:
            True if a row existed and was deleted, False otherwise.
        """
        stmt = sa_delete(TempDriverGrant).where(TempDriverGrant.discord_user_id == discord_user_id)
        result = await session.execute(stmt)
        return result.rowcount > 0
