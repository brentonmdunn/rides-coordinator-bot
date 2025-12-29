"""Group Rides API Routes - Example Backend with Hardcoded Data."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.dummy_data import GROUP_RIDES_FRIDAY, GROUP_RIDES_SUNDAY

router = APIRouter(prefix="/api/group-rides", tags=["group-rides"])


class GroupRidesRequest(BaseModel):
    """Request model for grouping rides."""

    ride_type: str  # "friday", "sunday", or "message_id"
    message_id: str | None = None
    driver_capacity: str = "44444"
    channel_id: str = "939950319721406464"


class GroupRidesResponse(BaseModel):
    """Response model for grouped rides."""

    success: bool
    summary: str | None = None
    groupings: list[str] | None = None
    error: str | None = None


@router.post("", response_model=GroupRidesResponse)
async def group_rides(request: GroupRidesRequest):
    """
    Group rides based on ride type.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    # Validate ride_type
    if request.ride_type not in ["friday", "sunday", "message_id"]:
        return GroupRidesResponse(
            success=False, error="ride_type must be 'friday', 'sunday', or 'message_id'"
        )

    # Return appropriate hardcoded groupings
    if request.ride_type == "friday":
        data = GROUP_RIDES_FRIDAY
    elif request.ride_type == "sunday":
        data = GROUP_RIDES_SUNDAY
    else:  # message_id
        # For custom message_id, return Friday data as default
        data = GROUP_RIDES_FRIDAY

    return GroupRidesResponse(
        success=True, summary=data["summary"], groupings=data["groupings"]
    )
