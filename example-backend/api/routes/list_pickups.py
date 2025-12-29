"""List Pickups API Routes - Example Backend with Hardcoded Data."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.dummy_data import FRIDAY_PICKUPS, SUNDAY_PICKUPS

router = APIRouter(prefix="/api/list-pickups", tags=["list-pickups"])


class ListPickupsRequest(BaseModel):
    """Request model for listing pickups."""

    ride_type: str  # "friday", "sunday", or "message_id"
    message_id: str | None = None
    channel_id: str = "939950319721406464"


class ListPickupsResponse(BaseModel):
    """Response model for pickup locations."""

    success: bool
    data: dict | None = None
    error: str | None = None


@router.post("", response_model=ListPickupsResponse)
async def list_pickups(request: ListPickupsRequest):
    """
    List pickup locations based on ride type.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    # Validate ride_type
    if request.ride_type not in ["friday", "sunday", "message_id"]:
        return ListPickupsResponse(
            success=False, error="ride_type must be 'friday', 'sunday', or 'message_id'"
        )

    # Return appropriate hardcoded data
    if request.ride_type == "friday":
        return ListPickupsResponse(success=True, data=FRIDAY_PICKUPS)
    elif request.ride_type == "sunday":
        return ListPickupsResponse(success=True, data=SUNDAY_PICKUPS)
    else:  # message_id
        # For custom message_id, return Friday data as default
        return ListPickupsResponse(success=True, data=FRIDAY_PICKUPS)
