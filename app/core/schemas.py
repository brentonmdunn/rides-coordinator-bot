from pydantic import BaseModel, field_validator
from app.core.enums import PickupLocations

class LocationQuery(BaseModel):
    start_location: PickupLocations
    end_location: PickupLocations

class RidesUser(BaseModel):
    name: str
    username: str
    location: PickupLocations

    @field_validator('username', mode='before')
    def add_at_symbol(cls, v: str) -> str:
        if not v.startswith('@'):
            return f'@{v}'
        return v
