"""
Route Builder API Endpoints

Provides API access to route building functionality:
- GET /api/pickup-locations: Returns available pickup locations
- POST /api/make-route: Generates route based on locations and leave time
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bot.api import get_bot
from bot.core.enums import PickupLocations
from bot.services.group_rides_service import GroupRidesService
from bot.utils.constants import MAP_LOCATIONS, get_map_links

logger = logging.getLogger(__name__)

router = APIRouter()


class MakeRouteRequest(BaseModel):
    """Request model for making a route."""

    locations: list[str] = Field(
        description="List of pickup location IDs/names to include in the route"
    )
    leave_time: str = Field(description="Desired departure time from campus (e.g. '1:30 PM')")


class MakeRouteResponse(BaseModel):
    """Response model for making a route."""

    success: bool = Field(description="Whether the route generation was successful")
    route: str | None = Field(
        default=None, description="The formatted Google Maps route URL or text"
    )
    error: str | None = Field(default=None, description="Error message if the request failed")


class PickupLocationItem(BaseModel):
    """Model for a single pickup location."""

    key: str = Field(description="The internal enum key for the location")
    value: str = Field(description="The human-readable display name for the location")


class PickupLocationsResponse(BaseModel):
    """Response model for pickup locations."""

    locations: list[PickupLocationItem] = Field(
        description="List of all available pickup locations"
    )
    map_links: dict[str, str] = Field(
        description="Mapping of location display names to Google Maps URLs"
    )
    coordinates: dict[str, dict[str, float]] = Field(
        description="Mapping of location display names to lat/lng objects"
    )


@router.get(
    "/api/pickup-locations",
    response_model=PickupLocationsResponse,
    summary="Get Pickup Locations",
    description="Get all available pickup locations, their map links, and physical coordinates.",
)
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

        # Generate map links from coordinates
        map_links = {loc.value: url for loc, url in get_map_links().items()}

        # Build coordinates dict keyed by location value
        coordinates = {
            loc.value: {"lat": lat, "lng": lng} for loc, (lat, lng) in MAP_LOCATIONS.items()
        }

        return PickupLocationsResponse(
            locations=locations, map_links=map_links, coordinates=coordinates
        )

    except Exception as e:
        logger.exception("Error fetching pickup locations")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch pickup locations: {e!s}"
        ) from e


@router.post(
    "/api/make-route",
    response_model=MakeRouteResponse,
    summary="Generate Route",
    description="Generate an optimized driving route via Google Maps based on specified locations and a leaving time.",
)
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
        logger.warning("Bot not ready")
        raise HTTPException(status_code=503, detail="Discord bot not ready")

    # Validate inputs
    if not request.locations:
        return MakeRouteResponse(success=False, error="At least one location must be provided")

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
        logger.exception("Error generating route")
        raise HTTPException(status_code=500, detail=f"Failed to generate route: {e!s}") from e
