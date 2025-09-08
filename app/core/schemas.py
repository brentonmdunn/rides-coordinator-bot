from pydantic import BaseModel, field_validator
from app.core.enums import PickupLocations

class LocationQuery(BaseModel):
    start_location: PickupLocations
    end_location: PickupLocations

class Identity(BaseModel):
    name: str
    username: str

    @field_validator('username', mode='before')
    def add_at_symbol(cls, v: str) -> str: # noqa: N805
        if not v.startswith('@'):
            return f'@{v}'
        return v


class RidesUser(BaseModel):
    """
    - identity: Identity
    - location: PickupLocations
    """
    identity: Identity
    location: PickupLocations

