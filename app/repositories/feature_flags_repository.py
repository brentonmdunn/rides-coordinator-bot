"""Data access layer for feature flag operations."""

from sqlalchemy import case, select, update

from app.core.database import AsyncSessionLocal
from app.core.enums import FeatureFlagNames
from app.core.models import FeatureFlags as FeatureFlagsModel


class FeatureFlagsRepository:
    """Handles database operations for feature flags."""

    @staticmethod
    async def get_feature_flag_status(feature_flag: FeatureFlagNames) -> bool | None:
        """Return whether a feature flag is enabled or None if it doesn't exist.

        Args:
            feature_flag: The feature flag enum.

        Returns:
            True if enabled, False if disabled, None if not found.
        """
        async with AsyncSessionLocal() as session:
            stmt = select(FeatureFlagsModel.enabled).where(
                FeatureFlagsModel.feature == feature_flag
            )
            result = await session.execute(stmt)
            feature_flag_model = result.one_or_none()
            return feature_flag_model[0] if feature_flag_model else None

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

    @staticmethod
    async def update_feature_flag(feature_name: str, enabled: bool) -> None:
        """Update a feature flag's enabled state.

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
