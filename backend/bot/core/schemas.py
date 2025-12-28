"""Pydantic schemas.

This module defines the Pydantic models used for data validation and serialization.
"""

from pydantic import BaseModel, RootModel, field_validator

from bot.core.enums import CampusLivingLocations, PickupLocations


class LocationQuery(BaseModel):
    """Schema for querying locations."""

    start_location: PickupLocations
    end_location: PickupLocations


class Identity(BaseModel):
    """Schema representing a user's identity."""

    name: str
    username: str | None = None

    @field_validator("username", mode="before")
    def add_at_symbol(cls, v: str) -> str:  # noqa: N805
        """Ensures the username starts with an '@' symbol."""
        if v and not v.startswith("@"):
            return f"@{v}"
        return v


class RidesUser(BaseModel):
    """Schema representing a user needing a ride.

    Attributes:
        identity: The user's identity (name and username).
        location: The user's living location.
    """

    identity: Identity
    location: CampusLivingLocations


class LLMPassenger(BaseModel):
    """Schema representing a passenger in the LLM output."""

    name: str
    location: PickupLocations


class LLMOutputNominal(RootModel[dict[str, list[LLMPassenger]]]):
    """A root model representing the entire assignment structure.

    The root of this model is a dictionary mapping driver names to lists of passengers.
    """

    pass  # No extra logic needed for basic validation


class LLMOutputError(RootModel[dict[str, str]]):
    """Schema representing an error output from the LLM."""

    pass


class Passenger(BaseModel):
    """Schema representing a passenger with full location details."""

    identity: Identity
    living_location: CampusLivingLocations
    pickup_location: PickupLocations
