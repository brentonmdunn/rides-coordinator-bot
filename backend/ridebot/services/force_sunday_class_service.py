"""Service layer for the "always send Sunday class" global setting."""

import logging

from ridebot.repositories.global_settings_repository import GlobalSettingsRepository
from ridebot.utils.cache import invalidate_namespace
from shared.core.database import AsyncSessionLocal
from shared.core.enums import CacheNamespace

logger = logging.getLogger(__name__)

FORCE_SUNDAY_CLASS_KEY = "force_sunday_class"


class ForceSundayClassService:
    """Owns reading and writing the setting that skips the Sunday class calendar check."""

    @staticmethod
    async def is_enabled() -> bool:
        """Return True when the scheduled Sunday class message should send regardless of the calendar."""
        async with AsyncSessionLocal() as session:
            value = await GlobalSettingsRepository.get(session, FORCE_SUNDAY_CLASS_KEY)
        return value == "true"

    @staticmethod
    async def set_enabled(enabled: bool) -> None:
        """Persist the setting and drop the cached dashboard status."""
        async with AsyncSessionLocal() as session:
            await GlobalSettingsRepository.set(
                session, FORCE_SUNDAY_CLASS_KEY, "true" if enabled else "false"
            )
        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
        logger.info("Force Sunday class set to %s", enabled)
