"""Service for managing non-Discord rides."""

import logging
from datetime import date

from sqlalchemy.exc import IntegrityError

from bot.core.database import AsyncSessionLocal
from bot.core.models import NonDiscordRides
from bot.repositories.non_discord_rides_repository import NonDiscordRidesRepository
from bot.utils.time_helpers import get_next_date_obj

logger = logging.getLogger(__name__)


class DuplicateRideError(Exception):
    """Raised when attempting to create a ride that already exists."""

    pass


class NonDiscordRidesService:
    """Service for handling non-Discord ride logic."""

    async def add_pickup(self, name: str, day: str, location: str) -> NonDiscordRides:
        """
        Adds a pickup for a non-Discord user.

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
            try:
                ride = NonDiscordRides(name=name, date=ride_date, location=location)
                return await NonDiscordRidesRepository.create_ride(session, ride)
            except IntegrityError:
                raise DuplicateRideError(f"Pickup for {name} on {day} already exists.")  # noqa B904

    async def remove_pickup(self, name: str, day: str) -> bool:
        """
        Removes a pickup for a non-Discord user.

        Args:
            name: Name of the person.
            day: Day of the pickup.

        Returns:
            True if the pickup was removed, False if not found.
        """
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            ride = await NonDiscordRidesRepository.get_ride(session, name, ride_date)
            if ride:
                await NonDiscordRidesRepository.delete_ride(session, ride)
                return True
            return False

    async def list_pickups(self, day: str) -> list[NonDiscordRides]:
        """
        Lists all pickups for a specific day.

        Args:
            day: The day to list pickups for.

        Returns:
            A list of NonDiscordRides objects.
        """
        ride_date = get_next_date_obj(day)
        async with AsyncSessionLocal() as session:
            return await NonDiscordRidesRepository.get_rides_by_date(session, ride_date)

    async def delete_past_pickups(self) -> int:
        """
        Deletes all pickups from past dates.

        Returns:
            The number of deleted pickups.
        """
        today = date.today()
        async with AsyncSessionLocal() as session:
            return await NonDiscordRidesRepository.delete_past_rides(session, today)
