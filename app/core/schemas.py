from pydantic import BaseModel
from app.core.enums import PickupLocations

class LocationQuery(BaseModel):
    start_location: PickupLocations
    end_location: PickupLocations