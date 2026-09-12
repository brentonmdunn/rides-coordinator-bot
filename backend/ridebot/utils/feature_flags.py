"""Feature flag helpers for code paths that can't use the `feature_flag_enabled` decorator."""

from shared.core.database import AsyncSessionLocal
from shared.core.enums import FeatureFlagNames
from shared.repositories.feature_flags_repository import FeatureFlagsRepository


async def is_flag_enabled(feature: FeatureFlagNames) -> bool:
    """
    Return whether a feature flag is enabled, checking the cache before the DB.

    Args:
        feature: The feature flag to check.

    Returns:
        True if the flag is enabled; False if disabled or missing.
    """
    if feature.value in FeatureFlagsRepository._cache:
        return FeatureFlagsRepository._cache[feature.value]
    async with AsyncSessionLocal() as session:
        status = await FeatureFlagsRepository.get_feature_flag_status(session, feature)
    return bool(status)
