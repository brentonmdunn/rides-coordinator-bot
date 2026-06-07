"""
Non-Discord rides management API endpoints.

Lets ride coordinators add/list/remove pickups for people who are not in Discord
(and therefore never react to the ride posts). Mirrors the ``/add-pickup``,
``/remove-pickup``, and ``/list-added-pickups`` slash commands.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth import require_ride_coordinator
from bot.core.enums import CampusLivingLocations
from bot.services.non_discord_rides_service import DuplicateRideError, NonDiscordRidesService
from bot.utils.constants import LSCC_DAYS, RIDE_REACTION_LABELS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/non-discord-rides", tags=["non-discord-rides"])

service = NonDiscordRidesService()

_VALID_DAYS = {day.value for day in LSCC_DAYS}
_VALID_EMOJIS = set(RIDE_REACTION_LABELS)


def _validate_day(day: str) -> str:
    """Validate that the day is an allowed LSCC ride day, returning the canonical value."""
    if day not in _VALID_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid day '{day}'. Allowed values: {', '.join(sorted(_VALID_DAYS))}.",
        )
    return day


def _validate_emoji(emoji: str | None) -> str | None:
    """Validate that the emoji (if provided) is an allowed ride-reaction emoji."""
    if emoji is not None and emoji not in _VALID_EMOJIS:
        raise HTTPException(status_code=400, detail=f"Invalid reaction emoji '{emoji}'.")
    return emoji


@router.get("/campus-locations")
async def get_campus_locations() -> list[str]:
    """Return all valid campus living location names."""
    return [loc.value for loc in CampusLivingLocations]


class NonDiscordRideResponse(BaseModel):
    """A single non-Discord pickup entry."""

    name: str
    day: str
    location: str | None
    emoji: str | None


class AddNonDiscordRideRequest(BaseModel):
    """Request model for adding a non-Discord pickup."""

    name: str = Field(min_length=1, description="Name of the person to pick up")
    day: str = Field(description="Ride day (e.g. 'Friday' or 'Sunday')")
    location: str = Field(min_length=1, description="Pickup location")
    emoji: str | None = Field(
        default=None, description="Optional ride-reaction emoji tag (e.g. lunch/no-lunch)"
    )


class RemoveNonDiscordRideRequest(BaseModel):
    """Request model for removing a non-Discord pickup."""

    name: str = Field(min_length=1, description="Name of the person to remove")
    day: str = Field(description="Ride day (e.g. 'Friday' or 'Sunday')")


@router.get("", dependencies=[Depends(require_ride_coordinator)])
async def list_non_discord_rides(
    day: str = Query(description="Ride day to list pickups for (e.g. 'Friday')"),
) -> list[NonDiscordRideResponse]:
    """List all non-Discord pickups for a given day."""
    _validate_day(day)
    try:
        rides = await service.list_pickups(day)
    except Exception as e:
        logger.exception("Failed to list non-Discord rides")
        raise HTTPException(status_code=500, detail="Failed to list pickups.") from e

    return [
        NonDiscordRideResponse(name=ride.name, day=day, location=ride.location, emoji=ride.emoji)
        for ride in rides
    ]


@router.post("", dependencies=[Depends(require_ride_coordinator)])
async def add_non_discord_ride(
    body: AddNonDiscordRideRequest, request: Request
) -> NonDiscordRideResponse:
    """Add a non-Discord pickup for the given day."""
    _validate_day(body.day)
    _validate_emoji(body.emoji)
    name = body.name.strip()
    location = body.location.strip()
    if not name or not location:
        raise HTTPException(status_code=400, detail="Name and location are required.")

    try:
        ride = await service.add_pickup(name, body.day, location, emoji=body.emoji)
    except DuplicateRideError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to add non-Discord ride")
        raise HTTPException(status_code=500, detail="Failed to add pickup.") from e

    user = getattr(request.state, "user", None) or {}
    logger.info(
        "Non-Discord pickup added: %s on %s by %s",
        name,
        body.day,
        user.get("email", "unknown"),
    )
    return NonDiscordRideResponse(
        name=ride.name, day=body.day, location=ride.location, emoji=ride.emoji
    )


@router.delete("", dependencies=[Depends(require_ride_coordinator)])
async def remove_non_discord_ride(body: RemoveNonDiscordRideRequest, request: Request):
    """Remove a non-Discord pickup for the given day."""
    _validate_day(body.day)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")

    try:
        removed = await service.remove_pickup(name, body.day)
    except Exception as e:
        logger.exception("Failed to remove non-Discord ride")
        raise HTTPException(status_code=500, detail="Failed to remove pickup.") from e

    if not removed:
        raise HTTPException(status_code=404, detail=f"No pickup found for {name} on {body.day}.")

    user = getattr(request.state, "user", None) or {}
    logger.info(
        "Non-Discord pickup removed: %s on %s by %s",
        name,
        body.day,
        user.get("email", "unknown"),
    )
    return {"ok": True}
