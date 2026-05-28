"""List Pickups API Routes."""

import logging

import discord
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import parse_int_param, require_bot, validate_ride_type
from bot.core.enums import AskRidesMessage, ChannelIds, JobName
from bot.services.locations_service import LocationsService
from bot.utils.custom_exceptions import NoMatchingMessageFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/list-pickups", tags=["list-pickups"])


class ListPickupsRequest(BaseModel):
    """Request model for listing pickups."""

    ride_type: str = Field(
        description="Type of ride to lookup. Allowed values: 'friday', 'sunday', or 'message_id'"
    )
    message_id: str | None = Field(
        default=None, description="Required only when ride_type is 'message_id'"
    )
    channel_id: str = Field(
        default=str(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)),
        description="Default to rides announcements channel",
    )


class ListPickupsResponse(BaseModel):
    """Response model for pickup locations."""

    success: bool = Field(description="Whether the query was successful")
    data: dict | None = Field(
        default=None, description="The returned housing groups and unknown users"
    )
    error: str | None = Field(default=None, description="Error message if the request failed")


@router.post(
    "",
    response_model=ListPickupsResponse,
    summary="List Pickups",
    description="Extracts and categorizes pickup locations from user reactions on a requested Discord message.",
)
async def list_pickups(request: ListPickupsRequest):
    """
    List pickup locations based on ride type (Friday, Sunday, or custom message ID).

    Args:
        request: Request containing ride_type, optional message_id, and channel_id

    Returns:
        ListPickupsResponse with success status and either pickup data or error message
    """
    try:
        bot = require_bot()
    except HTTPException:
        bot = None

    validate_ride_type(request.ride_type)
    channel_id_int = parse_int_param(request.channel_id, "Channel ID")

    # Custom message_id lookups always require a live bot (not pre-cached)
    if request.ride_type == "message_id":
        if bot is None:
            raise HTTPException(status_code=503, detail="Bot not initialized")
        if not request.message_id:
            raise HTTPException(
                status_code=400, detail="message_id is required when ride_type is 'message_id'"
            )
        message_id_int: int | None = parse_int_param(request.message_id, "Message ID")
    else:
        message_id_int = None

    try:
        locations_service = LocationsService(bot)

        if message_id_int is None:
            # Find the message for Friday or Sunday
            if request.ride_type == JobName.FRIDAY:
                ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            else:  # sunday
                ask_message = AskRidesMessage.SUNDAY_SERVICE

            if bot is not None:
                message_id_int = await locations_service.find_correct_message(
                    ask_message, channel_id_int
                )
                if message_id_int is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            f"Could not find the {request.ride_type} rides message. "
                            "It may not exist yet."
                        ),
                    )
                (
                    locations,
                    usernames_reacted,
                    location_found,
                ) = await locations_service.list_locations(
                    message_id=message_id_int, channel_id=channel_id_int
                )
            else:
                # Bot unavailable: serve from cache by passing day directly, which avoids
                # the bot.get_channel() call that the message_id path requires.
                (
                    locations,
                    usernames_reacted,
                    location_found,
                ) = await locations_service.list_locations(
                    day=request.ride_type, channel_id=channel_id_int
                )
        else:
            # Custom message_id (bot already verified above)
            locations, usernames_reacted, location_found = await locations_service.list_locations(
                message_id=message_id_int, channel_id=channel_id_int
            )

        # Use shared helper to group locations
        grouped_data = locations_service.group_locations_by_housing(
            locations, usernames_reacted, location_found
        )

        # Fetch users who reacted with ⬅️ (drive back)
        drive_back_usernames: set[str] = set()
        if bot is not None and message_id_int is not None:
            try:
                drive_back_usernames = await locations_service.get_drive_back_usernames(
                    channel_id_int, message_id_int
                )
            except Exception:
                logger.exception("Failed to fetch drive-back reactions; proceeding without them")

        # Format response data for frontend
        housing_groups = {}

        for group_name, group_data in grouped_data["groups"].items():
            # Only include groups that have people
            if group_data["count"] > 0:
                formatted_locations = {}

                for location, people in group_data["locations"].items():
                    formatted_locations[location] = [
                        {
                            "name": person[0],
                            "discord_username": str(person[1]) if person[1] else None,
                            "drive_back": person[1] in drive_back_usernames if person[1] else False,
                        }
                        for person in people
                    ]

                housing_groups[group_name] = {
                    "emoji": group_data["emoji"],
                    "count": group_data["count"],
                    "locations": formatted_locations,
                }

        response_data = {
            "housing_groups": housing_groups,
            "unknown_users": grouped_data["unknown_users"],
        }

        return ListPickupsResponse(success=True, data=response_data)

    except HTTPException:
        raise
    except AttributeError as e:
        if bot is None:
            raise HTTPException(
                status_code=503, detail="Bot not initialized and no cached data available"
            ) from None
        logger.exception("An unexpected error occurred while listing pickups")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from e
    except NoMatchingMessageFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=(f"Could not find the {request.ride_type} rides message. It may not exist yet."),
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except discord.NotFound as e:
        raise HTTPException(
            status_code=404, detail="Message not found. Please check the Message ID and try again."
        ) from e
    except discord.Forbidden as e:
        raise HTTPException(
            status_code=403,
            detail="Bot does not have permission to access this message or channel.",
        ) from e
    except Exception as e:
        logger.exception("An unexpected error occurred while listing pickups")
        raise HTTPException(status_code=500, detail="An unexpected error occurred.") from e
