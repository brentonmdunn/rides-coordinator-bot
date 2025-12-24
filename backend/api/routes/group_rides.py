"""Group Rides API Routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.api import get_bot
from bot.services.group_rides_service import GroupRidesService

router = APIRouter(prefix="/api/group-rides", tags=["group-rides"])


class GroupRidesRequest(BaseModel):
    """Request model for grouping rides."""
    
    ride_type: str  # "friday", "sunday", or "message_id"
    message_id: str | None = None  # Required only when ride_type is "message_id"
    driver_capacity: str = "44444"
    channel_id: str = "939950319721406464"  # Default to rides announcements channel


class GroupRidesResponse(BaseModel):
    """Response model for grouped rides."""
    
    success: bool
    summary: str | None = None
    groupings: list[str] | None = None
    error: str | None = None


@router.post("", response_model=GroupRidesResponse)
async def group_rides(request: GroupRidesRequest):
    """
    Group rides based on ride type (Friday, Sunday, or custom message ID).
    
    Args:
        request: Request containing ride_type, optional message_id, driver_capacity, and channel_id
        
    Returns:
        GroupRidesResponse with success status and either groupings or error message
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Validate ride_type
        if request.ride_type not in ["friday", "sunday", "message_id"]:
            return GroupRidesResponse(
                success=False,
                error="ride_type must be 'friday', 'sunday', or 'message_id'"
            )
        
        # If using message_id, validate it's provided
        if request.ride_type == "message_id":
            if not request.message_id:
                return GroupRidesResponse(
                    success=False,
                    error="message_id is required when ride_type is 'message_id'"
                )
            try:
                message_id_int = int(request.message_id)
            except ValueError:
                return GroupRidesResponse(
                    success=False,
                    error="Message ID must be a valid integer"
                )
        else:
            message_id_int = None
        
        # Convert channel_id to int
        try:
            channel_id_int = int(request.channel_id)
        except ValueError:
            return GroupRidesResponse(
                success=False,
                error="Channel ID must be a valid integer"
            )
        
        # Create service and call the API method
        service = GroupRidesService(bot)
        result = await service.group_rides_api(
            message_id=message_id_int,
            day=request.ride_type if request.ride_type in ["friday", "sunday"] else None,
            driver_capacity=request.driver_capacity,
            channel_id=channel_id_int
        )
        
        return GroupRidesResponse(
            success=True,
            summary=result.get("summary"),
            groupings=result.get("groupings")
        )
        
    except ValueError as e:
        return GroupRidesResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        return GroupRidesResponse(
            success=False,
            error=f"An unexpected error occurred: {str(e)}"
        )
