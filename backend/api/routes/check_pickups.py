"""Check Pickups API Routes."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bot.api import get_bot
from bot.core.enums import AskRidesMessage, ChannelIds, JobName
from bot.repositories.ride_coverage_repository import RideCoverageRepository
from bot.services.locations_service import LocationsService
from bot.utils.time_helpers import get_last_sunday

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
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Validate ride_type
    if ride_type.lower() not in [JobName.FRIDAY, JobName.SUNDAY]:
        raise HTTPException(status_code=400, detail="ride_type must be 'friday' or 'sunday'")

    try:
        locations_service = LocationsService(bot)
        ride_coverage_repo = RideCoverageRepository()

        # Determine which message to check based on ride type
        if ride_type.lower() == JobName.FRIDAY:
            ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
        else:  # sunday
            ask_message = AskRidesMessage.SUNDAY_SERVICE

        # Find the most recent message for this ride type
        message_id = await locations_service._find_correct_message(
            ask_message, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        )

        if message_id is None:
            # No message found for this ride type yet
            return {
                "users": [],
                "total": 0,
                "assigned": 0,
                "message_found": False,
                "has_coverage_entries": False,
            }

        # Get all users who reacted to the message
        usernames_reacted = await locations_service._get_usernames_who_reacted(
            int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS), message_id
        )

        # For Sunday, exclude users going to class
        if ride_type.lower() == JobName.SUNDAY:
            class_message_id = await locations_service._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )
            if class_message_id:
                class_usernames = await locations_service._get_usernames_who_reacted(
                    int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS), class_message_id
                )
                usernames_reacted -= class_usernames

        # Build user list with assignment status using the repository
        # Use bulk check for performance
        usernames_list = [str(u) for u in usernames_reacted]
        covered_usernames = await ride_coverage_repo.get_bulk_coverage_status(usernames_list)

        users = []
        assigned_count = 0

        for username in usernames_list:
            has_ride = username in covered_usernames
            if has_ride:
                assigned_count += 1

            users.append({"discord_username": username, "has_ride": has_ride})

        # Sort: unassigned first, then alphabetically
        users.sort(key=lambda x: (x["has_ride"], x["discord_username"]))

        # Check if any coverage entries exist for the current week
        last_sunday = get_last_sunday()
        has_entries = await ride_coverage_repo.has_coverage_entries(last_sunday)

        return {
            "users": users,
            "total": len(users),
            "assigned": assigned_count,
            "message_found": True,
            "has_coverage_entries": has_entries,
        }

    except Exception as e:
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
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    try:
        # Get the RideCoverage cog
        ride_coverage_cog = bot.get_cog("RideCoverage")
        if not ride_coverage_cog:
            raise HTTPException(status_code=503, detail="RideCoverage cog not loaded")

        logger.info("API: Force sync ride coverage requested")
        result = await ride_coverage_cog.sync_ride_coverage()
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
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

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
    except Exception as e:
        logger.exception("Error fetching driver reactions")
        raise HTTPException(status_code=500, detail=str(e)) from e
