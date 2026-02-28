"""Job for synchronizing non-Discord rides."""

from bot.api import send_error_to_discord
from bot.core.logger import logger
from bot.services.non_discord_rides_service import NonDiscordRidesService


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
    except Exception:
        logger.exception("Unexpected error while deleting past pickups")
        await send_error_to_discord("**Unexpected Error** in `delete_past_pickups` job")
