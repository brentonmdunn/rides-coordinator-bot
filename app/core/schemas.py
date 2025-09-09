from pydantic import BaseModel, field_validator
from pydantic import BaseModel, RootModel, ValidationError
from app.core.enums import PickupLocations


class LocationQuery(BaseModel):
    start_location: PickupLocations
    end_location: PickupLocations


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
    location: PickupLocations


class Passenger(BaseModel):
    name: str
    location: PickupLocations

class LLMOutput(RootModel[dict[str, list[Passenger]]]):
    """
    A root model representing the entire assignment structure.
    The root of this model is a dictionary mapping driver names to lists of passengers.
    """
    pass # No extra logic needed for basic validation