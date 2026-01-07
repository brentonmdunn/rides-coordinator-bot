"""
Route Builder API Endpoints

Provides API access to route building functionality:
- GET /api/pickup-locations: Returns available pickup locations
- POST /api/make-route: Generates route based on locations and leave time
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.api import get_bot
from bot.core.enums import PickupLocations
from bot.services.group_rides_service import GroupRidesService
from bot.utils.constants import MAP_LINKS

logger = logging.getLogger(__name__)
router = APIRouter()


class MakeRouteRequest(BaseModel):
    """Request model for making a route."""

    locations: list[str]
    leave_time: str


class MakeRouteResponse(BaseModel):
    """Response model for making a route."""

    success: bool
    route: str | None = None
    error: str | None = None


class PickupLocationItem(BaseModel):
    """Model for a single pickup location."""

    key: str
    value: str


class PickupLocationsResponse(BaseModel):
    """Response model for pickup locations."""

    locations: list[PickupLocationItem]
    map_links: dict[str, str]


@router.get("/api/pickup-locations", response_model=PickupLocationsResponse)
async def get_pickup_locations():
    """
    Get all available pickup locations and their Google Maps links.

    Returns:
        JSON with list of locations and map links

    Raises:
        HTTPException: If there's an error fetching locations
    """
    try:
        # Convert enum to list of location items
        locations = [
            PickupLocationItem(key=location.name, value=location.value)
            for location in PickupLocations
        ]

        # Convert MAP_LINKS to use location values as keys (string keys for JSON)
        map_links = {location.value: url for location, url in MAP_LINKS.items()}

        return PickupLocationsResponse(locations=locations, map_links=map_links)

    except Exception as e:
        logger.exception(f"Error fetching pickup locations: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pickup locations: {e!s}"
        ) from e


@router.post("/api/make-route", response_model=MakeRouteResponse)
async def make_route(request: MakeRouteRequest):
    """
    Generate a route based on specified locations and leave time.

    Args:
        request: MakeRouteRequest with locations and leave_time

    Returns:
        JSON with success status, route string, or error message

    Raises:
        HTTPException: If bot not ready or invalid parameters
    """
    logger.info(
        f"🚗 Make route endpoint called with locations={request.locations}, "
        f"leave_time={request.leave_time}"
    )

    bot = get_bot()

    if bot is None or not bot.is_ready():
        logger.error("Bot not ready")
        raise HTTPException(status_code=503, detail="Discord bot not ready")

    # Validate inputs
    if not request.locations:
        return MakeRouteResponse(
            success=False, error="At least one location must be provided"
        )

    if not request.leave_time:
        return MakeRouteResponse(success=False, error="Leave time must be provided")

    try:
        service = GroupRidesService(bot)

        # Convert locations list to space-separated string (as expected by make_route)
        locations_str = " ".join(request.locations)

        # Call the existing make_route method
        route = service.make_route(locations_str, request.leave_time)

        logger.info(f"✅ Successfully generated route: {route}")
        return MakeRouteResponse(success=True, route=route)

    except ValueError as e:
        logger.warning(f"Invalid input for route generation: {e}")
        return MakeRouteResponse(success=False, error=str(e))

    except Exception as e:
        logger.exception(f"Error generating route: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate route: {e!s}"
        ) from e
