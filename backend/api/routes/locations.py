"""
Locations API Endpoints

Provides API access to location/pickup listing functionality.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from bot.api import get_bot
from bot.core.enums import ChannelIds
from bot.services.locations_service import LocationsService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/locations/pickups-by-message")
async def get_pickups_by_message(
    message_id: str = Query(..., description="The Discord message ID"),
    channel_id: str = Query(
        default=str(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS),
        description="The Discord channel ID",
    ),
):
    """
    Get pickup locations based on reactions to a Discord message.

    Args:
        message_id: Discord message ID to check reactions on
        channel_id: Discord channel ID where the message is located

    Returns:
        JSON with pickup locations grouped by housing and list of unknown users

    Raises:
        HTTPException: If bot not ready, invalid IDs, or message not found
    """
    logger.info(f"🔍 Pickups endpoint called with message_id={message_id}, channel_id={channel_id}")

    bot = get_bot()

    logger.info("here")

    if bot is None or not bot.is_ready():
        logger.error("Bot not ready")
        raise HTTPException(status_code=503, detail="Discord bot not ready")

    # Validate and convert IDs
    try:
        message_id_int = int(message_id)
        channel_id_int = int(channel_id)
        logger.info(f"Converted IDs: message_id={message_id_int}, channel_id={channel_id_int}")
    except ValueError:
        logger.error(f"Invalid IDs: message_id={message_id}, channel_id={channel_id}")
        raise HTTPException(
            status_code=400, detail="Message ID and Channel ID must be valid integers"
        ) from None

    # Create service and fetch locations
    try:
        service = LocationsService(bot)
        logger.info("Calling list_locations...")
        locations_people, usernames_reacted, location_found = await service.list_locations(
            message_id=message_id_int, channel_id=channel_id_int
        )

        logger.info(
            f"Got {len(locations_people)} locations, {len(usernames_reacted)} users reacted"
        )

        # Use the service's grouping helper to get structured data
        grouped_data = service._group_locations_by_housing(
            locations_people, usernames_reacted, location_found
        )

        # Convert to JSON-serializable format with better structure
        result = {"housing_groups": {}, "unknown_users": grouped_data["unknown_users"]}

        # Format the grouped data for JSON response
        for group_name, group_data in grouped_data["groups"].items():
            if group_data["count"] > 0:
                result["housing_groups"][group_name] = {
                    "emoji": group_data["emoji"],
                    "count": group_data["count"],
                    "locations": {},
                }

                # Convert locations dict to include discord usernames
                for location, people_names in group_data["locations"].items():
                    # Get full person info (name, username) from locations_people
                    people_with_usernames = []
                    for name in people_names:
                        # Find the matching person in locations_people
                        for person_tuple in locations_people.get(location, []):
                            if person_tuple[0] == name:
                                people_with_usernames.append(
                                    {
                                        "name": person_tuple[0],
                                        "discord_username": str(person_tuple[1])
                                        if person_tuple[1]
                                        else None,
                                    }
                                )
                                break

                    result["housing_groups"][group_name]["locations"][location] = (
                        people_with_usernames
                    )

        logger.info(
            f"✅ Returning grouped result with {len(result['housing_groups'])} housing groups"
        )
        return result

    except Exception as e:
        logger.exception(f"Error fetching pickups: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pickups: {e!s}") from e
