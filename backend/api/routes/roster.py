"""
People Roster Management API Endpoints

CRUD for the people roster (names, Discord identities, class year, and living
location). All endpoints require the ride coordinator role.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_ride_coordinator
from ridebot.services.roster_service import Person, PersonInput, RosterService
from ridebot.utils.custom_exceptions import (
    RosterConflictError,
    RosterNotFoundError,
    RosterValidationError,
)
from shared.utils.datetimes import to_iso_utc

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/roster",
    dependencies=[Depends(require_ride_coordinator)],
    tags=["roster"],
)

IdList = Annotated[list[int], Field(min_length=1, max_length=500)]


class PersonOut(BaseModel):
    """A roster entry."""

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
    """A list of roster entries."""

    people: list[PersonOut]


class RosterOptionsOut(BaseModel):
    """Valid class years and living locations for roster forms."""

    years: list[str]
    locations: list[str]


class CreatePersonRequest(BaseModel):
    """Request body for creating a roster entry."""

    name: str
    discord_username: str | None = None
    year: str | None = None
    location: str | None = None


class UpdatePersonRequest(BaseModel):
    """Request body for partially updating a roster entry."""

    name: str | None = None
    discord_username: str | None = None
    year: str | None = None
    location: str | None = None


class BulkDeleteRequest(BaseModel):
    """Request body for deleting multiple roster entries."""

    ids: IdList


class BulkDeleteResponse(BaseModel):
    """Response for a bulk-delete request."""

    deleted: int


@router.get("", response_model=PeopleOut, summary="List Roster")
async def list_roster():
    """Return every roster entry."""
    people = await RosterService.list_people()
    return PeopleOut(people=[PersonOut.from_person(p) for p in people])


@router.get("/options", response_model=RosterOptionsOut, summary="Get Roster Options")
async def get_roster_options():
    """Return the valid class years and living locations for roster forms."""
    options = RosterService.get_options()
    return RosterOptionsOut(years=options["years"], locations=options["locations"])


@router.post("", response_model=PersonOut, status_code=201, summary="Create Roster Entry")
async def create_person(request: CreatePersonRequest):
    """Create a new roster entry."""
    try:
        person = await RosterService.create_person(
            PersonInput(
                name=request.name,
                discord_username=request.discord_username,
                year=request.year,
                location=request.location,
            )
        )
    except RosterValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RosterConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to create roster entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return PersonOut.from_person(person)


@router.post("/bulk-delete", response_model=BulkDeleteResponse, summary="Bulk-Delete Roster")
async def bulk_delete_people(request: BulkDeleteRequest):
    """Delete multiple roster entries by id. Unknown ids are ignored."""
    try:
        deleted = await RosterService.delete_people(request.ids)
    except Exception:
        logger.exception("Failed to bulk-delete roster entries")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return BulkDeleteResponse(deleted=deleted)


@router.patch("/{person_id}", response_model=PersonOut, summary="Update Roster Entry")
async def update_person(person_id: int, request: UpdatePersonRequest):
    """Partially update a roster entry."""
    changes = request.model_dump(exclude_unset=True)
    try:
        person = await RosterService.update_person(person_id, changes)
    except RosterValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RosterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RosterConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to update roster entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
    return PersonOut.from_person(person)


@router.delete("/{person_id}", status_code=204, summary="Delete Roster Entry")
async def delete_person(person_id: int):
    """Delete a single roster entry."""
    try:
        await RosterService.get_person(person_id)
    except RosterNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        logger.exception("Failed to look up roster entry for deletion")
        raise HTTPException(status_code=500, detail="Internal server error") from None

    try:
        await RosterService.delete_people([person_id])
    except Exception:
        logger.exception("Failed to delete roster entry")
        raise HTTPException(status_code=500, detail="Internal server error") from None
