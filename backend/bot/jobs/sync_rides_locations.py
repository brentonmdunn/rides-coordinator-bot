from bot.core.enums import FeatureFlagNames
from bot.services.locations_service import LocationsService
from bot.utils.checks import feature_flag_enabled


@feature_flag_enabled(FeatureFlagNames.RIDES_LOCATIONS_SYNC_JOB)
async def sync_rides_locations():
    service = LocationsService(bot=None)
    await service.sync_locations()
