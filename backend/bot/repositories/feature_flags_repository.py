"""Data access layer for feature flag operations."""

from typing import ClassVar

from sqlalchemy import case, select, update

from bot.core.database import AsyncSessionLocal
from bot.core.enums import FeatureFlagNames
from bot.core.logger import logger
from bot.core.models import FeatureFlags as FeatureFlagsModel


class FeatureFlagsRepository:
    """Handles database operations for feature flags."""

    _cache: ClassVar[dict[str, bool]] = {}

    @classmethod
    async def initialize_cache(cls) -> None:
        """Load all feature flags into the cache."""
        async with AsyncSessionLocal() as session:
            stmt = select(FeatureFlagsModel)
            result = await session.execute(stmt)
            flags = result.scalars().all()
            cls._cache = {flag.feature: flag.enabled for flag in flags}
            logger.info(f"🚩 Feature flags cache initialized with {len(cls._cache)} flags.")

    @classmethod
    async def get_feature_flag_status(cls, feature_flag: FeatureFlagNames) -> bool | None:
        """Return whether a feature flag is enabled or None if it doesn't exist.

        Checks the local cache first before falling back to the database.

        Args:
            feature_flag: The feature flag enum.

        Returns:
            True if enabled, False if disabled, None if not found.
        """
        # Check cache first
        if feature_flag.value in cls._cache:
            return cls._cache[feature_flag.value]

        # Fallback to DB (should rarely happen if initialized)
        async with AsyncSessionLocal() as session:
            stmt = select(FeatureFlagsModel.enabled).where(
                FeatureFlagsModel.feature == feature_flag
            )
            result = await session.execute(stmt)
            feature_flag_model = result.one_or_none()

            if feature_flag_model:
                # Update cache if found
                cls._cache[feature_flag.value] = feature_flag_model[0]
                return feature_flag_model[0]
            return None

    @staticmethod
    async def get_feature_flag(feature_name: str):
        """Retrieve a feature flag model by its name.

        Args:
            feature_name: The name of the feature flag.

        Returns:
            The FeatureFlagsModel object if found, otherwise None.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(FeatureFlagsModel).where(FeatureFlagsModel.feature == feature_name)
            result = await session.execute(stmt)
            return result.scalars().first()

    @classmethod
    async def update_feature_flag(cls, feature_name: str, enabled: bool) -> None:
        """Update a feature flag's enabled state in both the database and cache.

        Args:
            feature_name: The name of the feature flag.
            enabled: The new enabled state.
        """
        async with AsyncSessionLocal() as session:
            stmt = (
                update(FeatureFlagsModel)
                .where(FeatureFlagsModel.feature == feature_name)
                .values(enabled=enabled)
            )
            await session.execute(stmt)
            await session.commit()

        # Update cache
        cls._cache[feature_name] = enabled

    @staticmethod
    async def get_all_feature_flags() -> list[FeatureFlagsModel]:
        """Return all feature flags, ordered with 'BOT' first then alphabetically.

        Returns:
            A list of FeatureFlagsModel objects.
        """
        async with AsyncSessionLocal() as session:
            order_logic = case(
                (FeatureFlagsModel.feature == FeatureFlagNames.BOT.value, 0),
                else_=1,
            )
            stmt = select(FeatureFlagsModel).order_by(order_logic, FeatureFlagsModel.feature)
            result = await session.execute(stmt)
            return result.scalars().all()
