"""Non-Discord Rides API Routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from bot.services.non_discord_rides_service import DuplicateRideError, NonDiscordRidesService

router = APIRouter(prefix="/api/non-discord-rides", tags=["non-discord-rides"])


class AddRideRequest(BaseModel):
    """Request model for adding a non-Discord ride."""

    name: str
    day: str
    location: str


class NonDiscordRideResponse(BaseModel):
    """Response model for a non-Discord ride."""

    name: str
    date: str
    location: str


class ListRidesResponse(BaseModel):
    """Response model for listing rides."""

    rides: list[NonDiscordRideResponse]


@router.get("/{day}", response_model=ListRidesResponse)
async def list_rides(day: str):
    """
    List non-Discord rides for a specific day.

    Args:
        day: "friday" or "sunday"

    Returns:
        List of rides.
    """
    service = NonDiscordRidesService()
    try:
        rides = await service.list_pickups(day)
        return ListRidesResponse(
            rides=[
                NonDiscordRideResponse(
                    name=ride.name,
                    date=ride.date.isoformat(),
                    location=ride.location,
                )
                for ride in rides
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=NonDiscordRideResponse)
async def add_ride(request: AddRideRequest):
    """
    Add a new non-Discord ride.

    Args:
        request: Ride details (name, day, location)

    Returns:
        The created ride.
    """
    service = NonDiscordRidesService()
    try:
        ride = await service.add_pickup(request.name, request.day, request.location)
        return NonDiscordRideResponse(
            name=ride.name,
            date=ride.date.isoformat(),
            location=ride.location,
        )
    except DuplicateRideError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def remove_ride(name: str = Query(...), day: str = Query(...)):
    """
    Remove a non-Discord ride.

    Args:
        name: Name of the person.
        day: Day of the pickup.

    Returns:
        Success message.
    """
    service = NonDiscordRidesService()
    try:
        success = await service.remove_pickup(name, day)
        if not success:
            raise HTTPException(status_code=404, detail="Ride not found")
        return {"message": "Ride removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
