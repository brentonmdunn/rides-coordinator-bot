"""Data access layer for global settings."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import GlobalSetting

logger = logging.getLogger(__name__)


class GlobalSettingsRepository:
    """Handles database operations for global key-value settings."""

    @staticmethod
    async def get(session: AsyncSession, key: str) -> str | None:
        """Return the value for a key, or None if not found."""
        stmt = select(GlobalSetting).where(GlobalSetting.key == key)
        result = await session.execute(stmt)
        row = result.scalars().first()
        return row.value if row else None

    @staticmethod
    async def set(session: AsyncSession, key: str, value: str) -> None:
        """Upsert a key-value pair."""
        stmt = select(GlobalSetting).where(GlobalSetting.key == key)
        result = await session.execute(stmt)
        row = result.scalars().first()
        if row:
            row.value = value
        else:
            session.add(GlobalSetting(key=key, value=value))
        await session.commit()
