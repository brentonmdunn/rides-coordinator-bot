"""
Pickup Info Management API Endpoints

CRUD for pickup info (names, Discord identities, class year, and living
location). All endpoints require the ride coordinator role.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_ride_coordinator
from ridebot.services.pickup_info_service import Person, PersonInput, PickupInfoService
from ridebot.utils.custom_exceptions import (
    PickupInfoConflictError,
    PickupInfoNotFoundError,
    PickupInfoValidationError,
)
from shared.utils.datetimes import to_iso_utc

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pickup-info",
    dependencies=[Depends(require_ride_coordinator)],
    tags=["pickup-info"],
)

IdList = Annotated[list[int], Field(min_length=1, max_length=500)]


class PersonOut(BaseModel):
    """A pickup info entry."""

    id: int
    name: str
    discord_username: str | None
    discord_user_id: str | None
    year: str | None
    location: str | None
    updated_at: str | None

    @classmethod
    def from_person(cls, person: Person) -> "PersonOut":
        """Build a `PersonOut` from a service-layer `Person`."""
        return cls(
            id=person.id,
            name=person.name,
            discord_username=person.discord_username,
            discord_user_id=person.discord_user_id,
            year=person.year,
            location=person.location,
            updated_at=to_iso_utc(person.updated_at),
        )


class PeopleOut(BaseModel):
    """A list of pickup info entries."""

    people: list[PersonOut]


class PickupInfoOptionsOut(BaseModel):
    """Valid class years and living locations for pickup info forms."""

    years: list[str]
    locations: list[str]


class CreatePersonRequest(BaseModel):
    """Request body for creating a pickup info entry."""

    name: str
    discord_username: str | None = None
    year: str | None = None
    location: str | None = None


class UpdatePersonRequest(BaseModel):
    """Request body for partially updating a pickup info entry."""

    name: str | None = None
    discord_username: str | None = None
    year: str | None = None
    location: str | None = None


class BulkDeleteRequest(BaseModel):
    """Request body for deleting multiple pickup info entries."""

    ids: IdList


class BulkDeleteResponse(BaseModel):
    """Response for a bulk-delete request."""

    deleted: int


@router.get("", response_model=PeopleOut, summary="List Pickup Info")
async def list_pickup_info():
    """Return every pickup info entry."""
    people = await PickupInfoService.list_people()
    return PeopleOut(people=[PersonOut.from_person(p) for p in people])


@router.get("/options", response_model=PickupInfoOptionsOut, summary="Get Pickup Info Options")
async def get_pickup_info_options():
    """Return the valid class years and living locations for pickup info forms."""
    options = PickupInfoService.get_options()
    return PickupInfoOptionsOut(years=options["years"], locations=options["locations"])


@router.post("", response_model=PersonOut, status_code=201, summary="Create Pickup Info Entry")
async def create_person(request: CreatePersonRequest):
    """Create a new pickup info entry."""
    try:
        person = await PickupInfoService.create_person(
            PersonInput(
                name=request.name,
                discord_username=request.discord_username,
                year=request.year,
                location=request.location,
            )
        )
    except PickupInfoValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PickupInfoConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to create pickup info entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return PersonOut.from_person(person)


@router.post("/bulk-delete", response_model=BulkDeleteResponse, summary="Bulk-Delete Pickup Info")
async def bulk_delete_people(request: BulkDeleteRequest):
    """Delete multiple pickup info entries by id. Unknown ids are ignored."""
    try:
        deleted = await PickupInfoService.delete_people(request.ids)
    except Exception:
        logger.exception("Failed to bulk-delete pickup info entries")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return BulkDeleteResponse(deleted=deleted)


@router.patch("/{person_id}", response_model=PersonOut, summary="Update Pickup Info Entry")
async def update_person(person_id: int, request: UpdatePersonRequest):
    """Partially update a pickup info entry."""
    changes = request.model_dump(exclude_unset=True)
    try:
        person = await PickupInfoService.update_person(person_id, changes)
    except PickupInfoValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PickupInfoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PickupInfoConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to update pickup info entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return PersonOut.from_person(person)


@router.delete("/{person_id}", status_code=204, summary="Delete Pickup Info Entry")
async def delete_person(person_id: int):
    """Delete a single pickup info entry."""
    try:
        await PickupInfoService.get_person(person_id)
    except PickupInfoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to look up pickup info entry for deletion")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    try:
        await PickupInfoService.delete_people([person_id])
    except Exception:
        logger.exception("Failed to delete pickup info entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
