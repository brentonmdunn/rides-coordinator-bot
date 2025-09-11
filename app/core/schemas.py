from pydantic import BaseModel, RootModel, field_validator

from app.core.enums import PickupLocations, LivingLocations


class LocationQuery(BaseModel):
    start_location: LivingLocations
    end_location: LivingLocations


class Identity(BaseModel):
    name: str
    username: str

    @field_validator("username", mode="before")
    def add_at_symbol(cls, v: str) -> str:  # noqa: N805
        if not v.startswith("@"):
            return f"@{v}"
        return v


class RidesUser(BaseModel):
    """
    - identity: Identity
    - location: PickupLocations
    """

    identity: Identity
    location: LivingLocations


class Passenger(BaseModel):
    name: str
    location: LivingLocations


class LLMOutputNominal(RootModel[dict[str, list[Passenger]]]):
    """
    A root model representing the entire assignment structure.
    The root of this model is a dictionary mapping driver names to lists of passengers.
    """

    pass  # No extra logic needed for basic validation

class LLMOutputError(RootModel[dict[str, str]]):
    pass