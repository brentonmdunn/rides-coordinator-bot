from app.core.enums import FeatureFlagNames
from app.utils.checks import feature_flag_enabled
from app.services.locations_service import LocationsService


@feature_flag_enabled(FeatureFlagNames.RIDES_LOCATIONS_SYNC_JOB)
async def sync_rides_locations():
    service = LocationsService(bot=None)
    await service.sync_locations()
