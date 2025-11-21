from datetime import date
from typing import List, Optional

from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.core.models import NonDiscordRides
from app.repositories.non_discord_rides_repository import NonDiscordRidesRepository
from app.utils.time_helpers import get_next_date_obj


class DuplicateRideError(Exception):
    """Raised when attempting to create a ride that already exists."""
    pass


class NonDiscordRidesService:
    def __init__(self):
        # No dependencies needed in init for now, as we create session per method
        pass

    async def add_pickup(self, name: str, day: str, location: str) -> NonDiscordRides:
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            try:
                ride = NonDiscordRides(name=name, date=ride_date, location=location)
                return await repo.create_ride(ride)
            except IntegrityError:
                raise DuplicateRideError(f"Pickup for {name} on {day} already exists.")

    async def remove_pickup(self, name: str, day: str) -> bool:
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            ride = await repo.get_ride(name, ride_date)
            if ride:
                await repo.delete_ride(ride)
                return True
            return False

    async def list_pickups(self, day: str) -> List[NonDiscordRides]:
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            return await repo.get_rides_by_date(ride_date)
