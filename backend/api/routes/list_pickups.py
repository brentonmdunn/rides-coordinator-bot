"""List Pickups API Routes."""

import discord
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.api import get_bot, send_error_to_discord
from bot.core.enums import AskRidesMessage
from bot.core.logger import logger
from bot.services.locations_service import LocationsService

router = APIRouter(prefix="/api/list-pickups", tags=["list-pickups"])


class ListPickupsRequest(BaseModel):
    """Request model for listing pickups."""

    ride_type: str  # "friday", "sunday", or "message_id"
    message_id: str | None = None  # Required only when ride_type is "message_id"
    channel_id: str = "939950319721406464"  # Default to rides announcements channel


class ListPickupsResponse(BaseModel):
    """Response model for pickup locations."""

    success: bool
    data: dict | None = None
    error: str | None = None


@router.post("", response_model=ListPickupsResponse)
async def list_pickups(request: ListPickupsRequest):
    """
    List pickup locations based on ride type (Friday, Sunday, or custom message ID).

    Args:
        request: Request containing ride_type, optional message_id, and channel_id

    Returns:
        ListPickupsResponse with success status and either pickup data or error message
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    try:
        # Validate ride_type
        if request.ride_type not in ["friday", "sunday", "message_id"]:
            return ListPickupsResponse(
                success=False, error="ride_type must be 'friday', 'sunday', or 'message_id'"
            )

        # Convert channel_id to int
        try:
            channel_id_int = int(request.channel_id)
        except ValueError:
            return ListPickupsResponse(success=False, error="Channel ID must be a valid integer")

        # Determine message_id based on ride_type
        if request.ride_type == "message_id":
            if not request.message_id:
                return ListPickupsResponse(
                    success=False, error="message_id is required when ride_type is 'message_id'"
                )
            try:
                message_id_int = int(request.message_id)
            except ValueError:
                return ListPickupsResponse(
                    success=False, error="Message ID must be a valid integer"
                )
        else:
            # Find the message for Friday or Sunday
            if request.ride_type == "friday":
                ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            else:  # sunday
                ask_message = AskRidesMessage.SUNDAY_SERVICE

            locations_service = LocationsService(bot)
            message_id_int = await locations_service._find_correct_message(
                ask_message, channel_id_int
            )

            if message_id_int is None:
                return ListPickupsResponse(
                    success=False,
                    error=(
                        f"Could not find the {request.ride_type} rides message. "
                        "It may not exist yet."
                    ),
                )

        # Get pickup locations
        locations_service = LocationsService(bot)
        locations, usernames_reacted, location_found = await locations_service.list_locations(
            message_id=message_id_int, channel_id=channel_id_int
        )

        # Use shared helper to group locations
        grouped_data = locations_service.group_locations_by_housing(
            locations, usernames_reacted, location_found
        )

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

    except ValueError as e:
        return ListPickupsResponse(success=False, error=str(e))
    except discord.NotFound:
        return ListPickupsResponse(
            success=False, error="Message not found. Please check the Message ID and try again."
        )
    except discord.Forbidden:
        return ListPickupsResponse(
            success=False, error="Bot does not have permission to access this message or channel."
        )
    except Exception as e:
        logger.exception("An unexpected error occurred while listing pickups")
        await send_error_to_discord("**Uncaught API Error** in `/api/list-pickups`", error=e)
        return ListPickupsResponse(success=False, error=f"An unexpected error occurred: {e!s}")
