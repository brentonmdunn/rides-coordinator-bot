"""Database configuration and initialization.

This module handles the database connection, session creation, and initialization routines.
"""

import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.core.base import Base
from bot.core.enums import FeatureFlagNames, JobName
from bot.core.logger import logger
from bot.core.models import FeatureFlags, MessageSchedulePause

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./db/bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Initializes the database by creating all tables defined in the metadata."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_feature_flags(session: AsyncSession):
    """Ensures that all feature flags defined in the enum exist in the database.

    If a flag doesn't exist, it's created with a default 'disabled' state.

    Args:
        session: The database session to use for querying and adding flags.
    """
    for flag_name in FeatureFlagNames:
        result = await session.execute(
            select(FeatureFlags).where(FeatureFlags.feature == flag_name.value)
        )
        existing_flag = result.scalars().first()

        if not existing_flag:
            new_flag = FeatureFlags(feature=flag_name.value)  # `enabled` defaults to False
            session.add(new_flag)
            logger.info(f"🚩 Created feature flag '{flag_name.value}' (disabled by default).")

    await session.commit()


async def seed_message_schedule_pauses(session: AsyncSession):
    """Ensures that all message schedule pause rows exist in the database.

    If a row doesn't exist for a job, it's created with a default un-paused state.

    Args:
        session: The database session to use for querying and adding rows.
    """
    for job_name in JobName:
        result = await session.execute(
            select(MessageSchedulePause).where(MessageSchedulePause.job_name == job_name)
        )
        existing = result.scalars().first()

        if not existing:
            new_pause = MessageSchedulePause(job_name=job_name, is_paused=False)
            session.add(new_pause)
            logger.info(f"⏸️ Created message schedule pause for '{job_name}' (active by default).")

    await session.commit()
