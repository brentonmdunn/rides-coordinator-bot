"""Repository for the people roster (the ``locations`` table)."""

import logging
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.models import Locations

logger = logging.getLogger(__name__)


class RosterRepository:
    """Handles database operations for the people roster."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[Locations]:
        """Return every roster entry, ordered by name (case-insensitive)."""
        stmt = select(Locations).order_by(func.lower(Locations.name))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, person_id: int) -> Locations | None:
        """Return the roster entry with ``person_id``, or ``None``."""
        stmt = select(Locations).where(Locations.id == person_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_ids(session: AsyncSession, ids: list[int]) -> list[Locations]:
        """Return the roster entries whose id is in ``ids``."""
        if not ids:
            return []
        stmt = select(Locations).where(Locations.id.in_(ids))
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_discord_user_id(
        session: AsyncSession, discord_user_id: str
    ) -> Locations | None:
        """Return the roster entry linked to ``discord_user_id``, or ``None``."""
        stmt = select(Locations).where(Locations.discord_user_id == discord_user_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_by_discord_username(session: AsyncSession, username: str) -> Locations | None:
        """Return the roster entry whose Discord username matches ``username`` (case-insensitive)."""
        stmt = select(Locations).where(func.lower(Locations.discord_username) == username.lower())
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        name: str,
        discord_username: str | None,
        discord_user_id: str | None,
        year: str | None,
        location: str | None,
        updated_at: datetime,
    ) -> Locations:
        """Create and flush a new roster entry."""
        person = Locations(
            name=name,
            discord_username=discord_username,
            discord_user_id=discord_user_id,
            year=year,
            location=location,
            updated_at=updated_at,
        )
        session.add(person)
        await session.flush()
        return person

    @staticmethod
    async def delete_by_ids(session: AsyncSession, ids: list[int]) -> int:
        """Delete roster entries by id and return how many were deleted."""
        if not ids:
            return 0
        stmt = delete(Locations).where(Locations.id.in_(ids))
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount or 0
