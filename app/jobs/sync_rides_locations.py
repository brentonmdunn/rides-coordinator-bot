from app.core.enums import FeatureFlagNames
from app.utils.checks import feature_flag_enabled
from app.utils.lookups import sync


@feature_flag_enabled(FeatureFlagNames.RIDES_LOCATIONS_SYNC_JOB)
async def sync_rides_locations():
    await sync()
