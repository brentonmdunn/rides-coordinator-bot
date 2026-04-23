"""Data access layer for feature flag operations."""

import logging
from typing import ClassVar

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import FeatureFlagNames
from bot.core.models import FeatureFlags as FeatureFlagsModel

logger = logging.getLogger(__name__)


class FeatureFlagsRepository:
    """Handles database operations for feature flags."""

    _cache: ClassVar[dict[str, bool]] = {}

    @staticmethod
    async def initialize_cache(session: AsyncSession) -> None:
        """Load all feature flags into the cache."""
        stmt = select(FeatureFlagsModel)
        result = await session.execute(stmt)
        flags = result.scalars().all()
        FeatureFlagsRepository._cache = {flag.feature: flag.enabled for flag in flags}
        logger.info(
            f"🚩 Feature flags cache initialized with {len(FeatureFlagsRepository._cache)} flags."
        )

    @staticmethod
    async def get_feature_flag_status(
        session: AsyncSession, feature_flag: FeatureFlagNames
    ) -> bool | None:
        """
        Return whether a feature flag is enabled or None if it doesn't exist.

        Checks the local cache first before falling back to the database.

        Args:
            session: The database session.
            feature_flag: The feature flag enum.

        Returns:
            True if enabled, False if disabled, None if not found.
        """
        if feature_flag.value in FeatureFlagsRepository._cache:
            return FeatureFlagsRepository._cache[feature_flag.value]

        stmt = select(FeatureFlagsModel.enabled).where(FeatureFlagsModel.feature == feature_flag)
        result = await session.execute(stmt)
        feature_flag_model = result.one_or_none()

        if feature_flag_model:
            FeatureFlagsRepository._cache[feature_flag.value] = feature_flag_model[0]
            return feature_flag_model[0]
        return None

    @staticmethod
    async def get_feature_flag(session: AsyncSession, feature_name: str):
        """
        Retrieve a feature flag model by its name.

        Args:
            session: The database session.
            feature_name: The name of the feature flag.

        Returns:
            The FeatureFlagsModel object if found, otherwise None.
        """
        stmt = select(FeatureFlagsModel).where(FeatureFlagsModel.feature == feature_name)
        result = await session.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def update_feature_flag(session: AsyncSession, feature_name: str, enabled: bool) -> None:
        """
        Update a feature flag's enabled state in both the database and cache.

        Args:
            session: The database session.
            feature_name: The name of the feature flag.
            enabled: The new enabled state.
        """
        stmt = (
            update(FeatureFlagsModel)
            .where(FeatureFlagsModel.feature == feature_name)
            .values(enabled=enabled)
        )
        await session.execute(stmt)
        await session.commit()

        FeatureFlagsRepository._cache[feature_name] = enabled

    @staticmethod
    async def get_all_feature_flags(session: AsyncSession) -> list[FeatureFlagsModel]:
        """
        Return all feature flags, ordered with 'BOT' first then alphabetically.

        Args:
            session: The database session.

        Returns:
            A list of FeatureFlagsModel objects.
        """
        order_logic = case(
            (FeatureFlagsModel.feature == FeatureFlagNames.BOT.value, 0),
            else_=1,
        )
        stmt = select(FeatureFlagsModel).order_by(order_logic, FeatureFlagsModel.feature)
        result = await session.execute(stmt)
        return result.scalars().all()
