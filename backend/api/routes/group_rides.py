"""Group Rides API Routes."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.dependencies import parse_int_param, require_bot, validate_ride_type
from api.rate_limit import limiter
from bot.core.enums import ChannelIds, JobName
from bot.services.group_rides_service import GroupRidesService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/group-rides", tags=["group-rides"])


class GroupRidesRequest(BaseModel):
    """Request model for grouping rides."""

    ride_type: str = Field(description="Type of ride (e.g. 'friday', 'sunday', or 'message_id')")
    message_id: str | None = Field(
        default=None, description="Required only when ride_type is 'message_id'"
    )
    driver_capacity: str = Field(
        default="44444", description="String of integers representing seats per driver"
    )
    channel_id: str = Field(
        default=str(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)),
        description="Default to rides announcements channel",
    )


class GroupRidesResponse(BaseModel):
    """Response model for grouped rides."""

    success: bool = Field(description="Whether the grouping was successful")
    summary: str | None = Field(
        default=None, description="String summary of the total drivers and passengers"
    )
    groupings: list[str] | None = Field(
        default=None, description="List of formatted strings representing each car grouping"
    )
    error: str | None = Field(default=None, description="Error message if the request failed")


@router.post(
    "",
    response_model=GroupRidesResponse,
    summary="Group Rides",
    description="Automatically group people from pickup locations into cars based on driver capacity.",
)
@limiter.limit("10/minute")
async def group_rides(request: Request, body: GroupRidesRequest):
    """
    Group rides based on ride type (Friday, Sunday, or custom message ID).

    Args:
        request: FastAPI request (required by slowapi for rate limiting).
        body: Request body containing ride_type, optional message_id,
            driver_capacity, and channel_id.

    Returns:
        GroupRidesResponse with success status and either groupings or error message
    """
    bot = require_bot()
    validate_ride_type(body.ride_type)
    channel_id_int = parse_int_param(body.channel_id, "Channel ID")

    if body.ride_type == "message_id":
        if not body.message_id:
            raise HTTPException(
                status_code=400, detail="message_id is required when ride_type is 'message_id'"
            )
        message_id_int: int | None = parse_int_param(body.message_id, "Message ID")
    else:
        message_id_int = None

    try:
        # Create service and call the API method
        service = GroupRidesService(bot)
        result = await service.group_rides_api(
            message_id=message_id_int,
            day=body.ride_type if body.ride_type in [JobName.FRIDAY, JobName.SUNDAY] else None,
            driver_capacity=body.driver_capacity,
            channel_id=channel_id_int,
        )

        return GroupRidesResponse(
            success=True, summary=result.get("summary"), groupings=result.get("groupings")
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Unexpected error in group_rides API")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from e
