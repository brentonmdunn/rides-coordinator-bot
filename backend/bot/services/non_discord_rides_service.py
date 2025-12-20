"""Service for managing non-Discord rides."""

from datetime import date

from sqlalchemy.exc import IntegrityError

from bot.core.database import AsyncSessionLocal
from bot.core.models import NonDiscordRides
from bot.repositories.non_discord_rides_repository import NonDiscordRidesRepository
from bot.utils.time_helpers import get_next_date_obj


class DuplicateRideError(Exception):
    """Raised when attempting to create a ride that already exists."""

    pass


class NonDiscordRidesService:
    """Service for handling non-Discord ride logic."""

    def __init__(self):
        # No dependencies needed in init for now, as we create session per method
        pass

    async def add_pickup(self, name: str, day: str, location: str) -> NonDiscordRides:
        """Adds a pickup for a non-Discord user.

        Args:
            name: Name of the person.
            day: Day of the pickup (e.g., "Friday", "Sunday").
            location: Pickup location.

        Returns:
            The created NonDiscordRides object.

        Raises:
            DuplicateRideError: If a ride for the person on that day already exists.
        """
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            try:
                ride = NonDiscordRides(name=name, date=ride_date, location=location)
                return await repo.create_ride(ride)
            except IntegrityError:
                raise DuplicateRideError(f"Pickup for {name} on {day} already exists.")  # noqa B904

    async def remove_pickup(self, name: str, day: str) -> bool:
        """Removes a pickup for a non-Discord user.

        Args:
            name: Name of the person.
            day: Day of the pickup.

        Returns:
            True if the pickup was removed, False if not found.
        """
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            ride = await repo.get_ride(name, ride_date)
            if ride:
                await repo.delete_ride(ride)
                return True
            return False

    async def list_pickups(self, day: str) -> list[NonDiscordRides]:
        """Lists all pickups for a specific day.

        Args:
            day: The day to list pickups for.

        Returns:
            A list of NonDiscordRides objects.
        """
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            return await repo.get_rides_by_date(ride_date)

    async def delete_past_pickups(self) -> int:
        """Deletes all pickups from past dates.

        Returns:
            The number of deleted pickups.
        """
        today = date.today()
        async with AsyncSessionLocal() as session:
            repo = NonDiscordRidesRepository(session)
            return await repo.delete_past_rides(today)
