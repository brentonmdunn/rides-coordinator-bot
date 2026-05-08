"""Check Pickups API Routes."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import require_bot, validate_ride_type
from bot.core.enums import AskRidesMessage, JobName
from bot.services.locations_service import LocationsService
from bot.services.ride_coverage_service import RideCoverageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/check-pickups", tags=["check-pickups"])


class PickupCoverageUser(BaseModel):
    """A single user's ride-assignment status."""

    discord_username: str = Field(description="The user's Discord username")
    has_ride: bool = Field(description="Whether the user has been assigned a ride")


class PickupCoverageResponse(BaseModel):
    """Response payload for the pickup-coverage endpoint."""

    users: list[PickupCoverageUser] = Field(description="List of users needing rides")
    total: int = Field(description="Total number of users who reacted")
    assigned: int = Field(description="Number of users who have been grouped into rides")
    message_found: bool = Field(description="Whether the original ask-rides message was found")
    has_coverage_entries: bool = Field(description="Whether coverage data exists for this week")


class SyncCoverageResponse(BaseModel):
    """Response payload for the sync-coverage endpoint."""

    success: bool = Field(description="Whether the sync was successful")
    message: str = Field(description="Status message")
    synced: int | None = Field(default=None, description="Number of usernames synced")
    errors: list[str] | None = Field(default=None, description="List of errors during sync")


class DriverReactionResponse(BaseModel):
    """Response payload for the driver-reactions endpoint."""

    day: str = Field(description="The day requested")
    reactions: dict[str, list[str]] = Field(description="Mapping of emoji to list of usernames")
    username_to_name: dict[str, str] = Field(
        description="Mapping of discord usernames to real names"
    )
    message_found: bool = Field(description="Whether the driver chat message was found")


@router.get(
    "/{ride_type}",
    response_model=PickupCoverageResponse,
    summary="Get Pickup Coverage",
    description="Check ride assignment coverage for users who requested a ride.",
)
async def get_pickup_coverage(ride_type: str):
    """
    Check ride coverage for users who reacted to a ride message.

    Args:
        ride_type: Either "friday" or "sunday"

    Returns:
        Dictionary containing:
        - users: List of {discord_username: str, has_ride: bool}
        - total: Total number of users who reacted
        - assigned: Number of users with ride assignments
    """
    bot = require_bot()
    validate_ride_type(ride_type.lower(), allow_message_id=False)

    try:
        service = RideCoverageService(bot)
        return await service.get_coverage_summary(ride_type.lower())
    except Exception as e:
        logger.exception("Failed to fetch ride coverage")
        raise HTTPException(status_code=500, detail=f"Failed to fetch ride coverage: {e!s}") from e


@router.post(
    "/sync",
    response_model=SyncCoverageResponse,
    summary="Sync Ride Coverage",
    description="Force sync ride coverage by scanning recent messages for assignments.",
)
async def sync_ride_coverage():
    """
    Force sync ride coverage by scanning recent messages.

    Returns:
        Dictionary with sync results.
    """
    bot = require_bot()

    try:
        logger.info("API: Force sync ride coverage requested")
        service = RideCoverageService(bot)
        result = await service.sync_ride_coverage()
        logger.info(f"API: Force sync completed: {result}")

        return {"success": True, "message": "Ride coverage sync completed", **result}

    except Exception as e:
        logger.exception("API: Failed to sync ride coverage")
        raise HTTPException(status_code=500, detail=f"Failed to sync ride coverage: {e!s}") from e


@router.get(
    "/driver-reactions/{day}",
    response_model=DriverReactionResponse,
    summary="Get Driver Reactions",
    description="Get emoji reactions from drivers offering rides in the driver chat.",
)
async def get_driver_reactions(day: str):
    """
    Get emoji reactions for driver messages.

    Args:
        day: "friday" or "sunday"
    """
    try:
        bot = require_bot()
    except HTTPException:
        bot = None

    locations_service = LocationsService(bot)
    try:
        if day.lower() == JobName.FRIDAY:
            event = AskRidesMessage.FRIDAY_FELLOWSHIP
        elif day.lower() == JobName.SUNDAY:
            event = AskRidesMessage.SUNDAY_SERVICE
        else:
            raise HTTPException(status_code=400, detail="Invalid day")

        result = await locations_service.get_driver_reactions(event)
        if result is None:
            return {"day": day, "reactions": {}, "username_to_name": {}, "message_found": False}
        return {
            "day": day,
            "reactions": result["reactions"],
            "username_to_name": result["username_to_name"],
            "message_found": True,
        }
    except HTTPException:
        raise
    except AttributeError as e:
        if bot is None:
            raise HTTPException(
                status_code=503, detail="Bot not initialized and no cached data available"
            ) from None
        logger.exception("Error fetching driver reactions")
        raise HTTPException(status_code=500, detail="Error fetching driver reactions") from e
    except Exception as e:
        logger.exception("Error fetching driver reactions")
        raise HTTPException(status_code=500, detail=str(e)) from e
