from app.core.logger import logger
from app.services.non_discord_rides_service import NonDiscordRidesService


async def delete_past_pickups():
    """
    Deletes all records from the NonDiscordRides table
    where the date is earlier than the current date.
    """
    service = NonDiscordRidesService()
    try:
        deleted_count = await service.delete_past_pickups()
        if deleted_count > 0:
            logger.info(f"Successfully deleted {deleted_count} past pickup entries.")
        else:
            logger.info("No past pickup entries found to delete.")
    except Exception as e:
        logger.error(f"An error occurred while deleting past pickups: {e}")
