"""Job for synchronizing ride locations."""

from bot.core.enums import FeatureFlagNames
from bot.core.logger import log_job
from bot.services.locations_service import LocationsService
from bot.utils.checks import feature_flag_enabled


@log_job
@feature_flag_enabled(FeatureFlagNames.RIDES_LOCATIONS_SYNC_JOB)
async def sync_rides_locations():
    """Synchronize ride locations from the repository."""
    service = LocationsService(bot=None)
    await service.sync_locations()
