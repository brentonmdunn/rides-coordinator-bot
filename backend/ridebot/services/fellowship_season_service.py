"""Service layer for the fellowship season global setting."""

import logging

from bot.core.database import AsyncSessionLocal
from bot.core.enums import CacheNamespace, FeatureFlagNames, FellowshipSeason
from bot.repositories.global_settings_repository import GlobalSettingsRepository
from bot.services.feature_flags_service import FeatureFlagsService
from bot.utils.cache import invalidate_namespace

logger = logging.getLogger(__name__)

FELLOWSHIP_SEASON_KEY = "fellowship_season"


class FellowshipSeasonService:
    """Owns reading and writing the fellowship season setting."""

    @staticmethod
    async def get_season() -> FellowshipSeason:
        """Return the active fellowship season (defaults to Friday)."""
        async with AsyncSessionLocal() as session:
            value = await GlobalSettingsRepository.get(session, FELLOWSHIP_SEASON_KEY)
        if not value:
            return FellowshipSeason.FRIDAY
        try:
            return FellowshipSeason(value)
        except ValueError:
            logger.warning("Unknown fellowship season %r; defaulting to friday", value)
            return FellowshipSeason.FRIDAY

    @staticmethod
    async def set_season(season: FellowshipSeason) -> None:
        """Persist the season and sync the Wed/Fri ask-rides feature flags to match."""
        svc = FeatureFlagsService()
        if season == FellowshipSeason.FRIDAY:
            enable_flag = FeatureFlagNames.ASK_FRIDAY_RIDES_JOB
            disable_flag = FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB
        else:
            enable_flag = FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB
            disable_flag = FeatureFlagNames.ASK_FRIDAY_RIDES_JOB

        async with AsyncSessionLocal() as session:
            await GlobalSettingsRepository.set(session, FELLOWSHIP_SEASON_KEY, season.value)
            await svc.modify_feature_flag(enable_flag.value, True, session)
            await svc.modify_feature_flag(disable_flag.value, False, session)
        await FeatureFlagsService.reinitialize_cache()
        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
        logger.info("Fellowship season set to %s", season.value)
