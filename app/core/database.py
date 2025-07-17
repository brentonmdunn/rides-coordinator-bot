# database.py
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.base import Base
from app.core.enums import FeatureFlagNames
from app.core.logger import logger
from app.core.models import FeatureFlags

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./db/bot.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_feature_flags(session: AsyncSession):
    """Ensures that all feature flags defined in the enum exist in the database.

    If a flag doesn't exist, it's created with a default 'disabled' state.
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
