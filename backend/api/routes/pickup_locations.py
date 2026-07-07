"""
Pickup Locations Management API Endpoints

CRUD for user-managed pickup locations, travel-time edges, living-location
mappings, and the pickup adjustment setting. All endpoints require the ride
coordinator role.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from api.auth import require_ride_coordinator
from bot.services.pickup_locations_service import PickupLocationsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pickup-locations",
    dependencies=[Depends(require_ride_coordinator)],
    tags=["pickup-locations"],
)

TrimmedName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]
Minutes = Annotated[int, Field(gt=0)]


class LocationOut(BaseModel):
    """A pickup location row."""

    id: int
    name: str
    latitude: float
    longitude: float
    minutes_from_start: int | None
    minutes_to_end: int | None
    is_active: bool
    is_seeded: bool


class EdgeOut(BaseModel):
    """A travel-time edge row."""

    id: int
    location_a_id: int
    location_b_id: int
    minutes: int


class LivingMappingOut(BaseModel):
    """A living-location → pickup-location mapping row."""

    living_location: str
    pickup_location_id: int


class PickupLocationsPayload(BaseModel):
    """Full management payload."""

    locations: list[LocationOut]
    edges: list[EdgeOut]
    living_mappings: list[LivingMappingOut]
    pickup_adjustment: int
    unreachable: list[str]


class CreateLocationRequest(BaseModel):
    """Request body for creating a pickup location."""

    name: TrimmedName
    latitude: Latitude
    longitude: Longitude
    minutes_from_start: Minutes | None = None
    minutes_to_end: Minutes | None = None


class UpdateLocationRequest(BaseModel):
    """Request body for partially updating a pickup location."""

    name: TrimmedName | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    minutes_from_start: Minutes | None = None
    minutes_to_end: Minutes | None = None
    is_active: bool | None = None


class UpsertEdgeRequest(BaseModel):
    """Request body for creating/updating a travel-time edge."""

    location_a_id: int
    location_b_id: int
    minutes: Minutes


class SetLivingMappingRequest(BaseModel):
    """Request body for pointing a living location at a pickup location."""

    pickup_location_id: int


class PickupAdjustmentRequest(BaseModel):
    """Request body for updating the pickup adjustment setting."""

    value: Annotated[int, Field(ge=0)]


class PickupAdjustmentResponse(BaseModel):
    """Response for the pickup adjustment setting."""

    value: int


@router.get("", response_model=PickupLocationsPayload, summary="Get Pickup Locations Payload")
async def get_pickup_locations():
    """Return all locations (incl. inactive), edges, mappings, and settings."""
    return await PickupLocationsService.get_all()


@router.post("", response_model=LocationOut, status_code=201, summary="Create Pickup Location")
async def create_pickup_location(request: CreateLocationRequest):
    """Create a new pickup location."""
    try:
        return await PickupLocationsService.create_location(
            name=request.name.strip(),
            latitude=request.latitude,
            longitude=request.longitude,
            minutes_from_start=request.minutes_from_start,
            minutes_to_end=request.minutes_to_end,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.patch("/{location_id}", response_model=LocationOut, summary="Update Pickup Location")
async def update_pickup_location(location_id: int, request: UpdateLocationRequest):
    """Partially update a pickup location (including reactivation)."""
    fields = request.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        fields["name"] = fields["name"].strip()
    try:
        location = await PickupLocationsService.update_location(location_id, **fields)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if location is None:
        raise HTTPException(status_code=404, detail=f"Unknown pickup location id {location_id}")
    return location


@router.delete("/{location_id}", status_code=204, summary="Deactivate Pickup Location")
async def delete_pickup_location(location_id: int):
    """Soft-delete (deactivate) a pickup location."""
    try:
        deleted = await PickupLocationsService.soft_delete_location(location_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Unknown pickup location id {location_id}")


@router.put("/edges", response_model=EdgeOut, summary="Upsert Travel-Time Edge")
async def upsert_edge(request: UpsertEdgeRequest):
    """Create or update the travel-time edge between two locations."""
    try:
        return await PickupLocationsService.upsert_edge(
            request.location_a_id, request.location_b_id, request.minutes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/edges/{edge_id}", status_code=204, summary="Delete Travel-Time Edge")
async def delete_edge(edge_id: int):
    """Delete a travel-time edge."""
    if not await PickupLocationsService.delete_edge(edge_id):
        raise HTTPException(status_code=404, detail=f"Unknown edge id {edge_id}")


@router.put(
    "/living-mappings/{living_location}",
    response_model=LivingMappingOut,
    summary="Set Living-Location Mapping",
)
async def set_living_mapping(living_location: str, request: SetLivingMappingRequest):
    """Point a campus living location at a pickup location."""
    try:
        return await PickupLocationsService.set_living_mapping(
            living_location, request.pickup_location_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put(
    "/settings/pickup-adjustment",
    response_model=PickupAdjustmentResponse,
    summary="Set Pickup Adjustment",
)
async def set_pickup_adjustment(request: PickupAdjustmentRequest):
    """Update the per-stop pickup time adjustment (minutes)."""
    value = await PickupLocationsService.set_pickup_adjustment(request.value)
    return PickupAdjustmentResponse(value=value)
