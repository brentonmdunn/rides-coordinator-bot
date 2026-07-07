"""
Route Builder API Endpoints

Provides API access to route building functionality:
- GET /api/map-locations: Active pickup locations with coordinates and map URLs
- POST /api/make-route: Generates route based on locations and leave time

(Coordinator-gated location management lives in api/routes/pickup_locations.py.)
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bot.services.pickup_locations_service import PickupLocationsService
from bot.services.route_service import RouteService

logger = logging.getLogger(__name__)

router = APIRouter()


class MapLocation(BaseModel):
    """An active pickup location with coordinates and a Google Maps URL."""

    name: str
    latitude: float
    longitude: float
    map_url: str


class MapLocationsResponse(BaseModel):
    """Response model for the map locations listing."""

    locations: list[MapLocation]


@router.get(
    "/api/map-locations",
    response_model=MapLocationsResponse,
    summary="List Map Locations",
    description="Active pickup locations with coordinates and Google Maps URLs.",
)
async def get_map_locations():
    """Return active pickup locations for map display (any authenticated user)."""
    routing = await PickupLocationsService.get_routing_context()
    return MapLocationsResponse(
        locations=[
            MapLocation(
                name=loc.name,
                latitude=loc.latitude,
                longitude=loc.longitude,
                map_url=url,
            )
            for loc in routing.locations
            if loc.is_active and (url := routing.map_url(loc.name)) is not None
        ]
    )


class MakeRouteRequest(BaseModel):
    """Request model for making a route."""

    locations: list[str] = Field(
        description="List of pickup location names to include in the route"
    )
    leave_time: str = Field(description="Desired departure time from campus (e.g. '1:30 PM')")


class MakeRouteResponse(BaseModel):
    """Response model for making a route."""

    success: bool = Field(description="Whether the route generation was successful")
    route: str | None = Field(
        default=None, description="The formatted Google Maps route URL or text"
    )
    error: str | None = Field(default=None, description="Error message if the request failed")


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

    # Validate inputs
    if not request.locations:
        raise HTTPException(status_code=400, detail="At least one location must be provided")

    if not request.leave_time:
        raise HTTPException(status_code=400, detail="Leave time must be provided")

    try:
        routing = await PickupLocationsService.get_routing_context()
        route = RouteService.make_route_from_names(routing, request.locations, request.leave_time)

        logger.info(f"✅ Successfully generated route: {route}")
        return MakeRouteResponse(success=True, route=route)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    except Exception as e:
        logger.exception("Error generating route")
        raise HTTPException(status_code=500, detail=f"Failed to generate route: {e!s}") from e
