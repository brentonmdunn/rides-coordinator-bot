"""Group Rides API Routes."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.dependencies import parse_int_param, require_bot, validate_ride_type
from bot.core.enums import ChannelIds, JobName
from bot.core.error_reporter import send_error_to_discord
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
async def group_rides(request: GroupRidesRequest):
    """
    Group rides based on ride type (Friday, Sunday, or custom message ID).

    Args:
        request: Request containing ride_type, optional message_id, driver_capacity, and channel_id

    Returns:
        GroupRidesResponse with success status and either groupings or error message
    """
    bot = require_bot()
    validate_ride_type(request.ride_type)
    channel_id_int = parse_int_param(request.channel_id, "Channel ID")

    if request.ride_type == "message_id":
        if not request.message_id:
            return GroupRidesResponse(
                success=False, error="message_id is required when ride_type is 'message_id'"
            )
        message_id_int: int | None = parse_int_param(request.message_id, "Message ID")
    else:
        message_id_int = None

    try:
        # Create service and call the API method
        service = GroupRidesService(bot)
        result = await service.group_rides_api(
            message_id=message_id_int,
            day=request.ride_type
            if request.ride_type in [JobName.FRIDAY, JobName.SUNDAY]
            else None,
            driver_capacity=request.driver_capacity,
            channel_id=channel_id_int,
        )

        return GroupRidesResponse(
            success=True, summary=result.get("summary"), groupings=result.get("groupings")
        )

    except ValueError as e:
        return GroupRidesResponse(success=False, error=str(e))
    except Exception:
        logger.exception("Unexpected error in group_rides API")
        await send_error_to_discord("**Unexpected Error** in `POST /api/group-rides`")
        return GroupRidesResponse(
            success=False, error="An unexpected error occurred. Please try again later."
        )
