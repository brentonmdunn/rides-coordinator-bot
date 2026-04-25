"""Service for managing non-Discord rides."""

import logging
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def add_pickup(
        self, name: str, day: str, location: str, session: AsyncSession | None = None
    ) -> NonDiscordRides:
        """
        Adds a pickup for a non-Discord user.

        Args:
            name: Name of the person.
            day: Day of the pickup (e.g., "Friday", "Sunday").
            location: Pickup location.
            session: Optional database session. If None, one is created internally.

        Returns:
            The created NonDiscordRides object.

        Raises:
            DuplicateRideError: If a ride for the person on that day already exists.
        """
        ride_date = get_next_date_obj(day)
        if session is not None:
            return await self._add_pickup(session, name, ride_date, location)

        async with AsyncSessionLocal() as session:
            return await self._add_pickup(session, name, ride_date, location)

    async def _add_pickup(
        self, session: AsyncSession, name: str, ride_date: date, location: str
    ) -> NonDiscordRides:
        try:
            ride = NonDiscordRides(name=name, date=ride_date, location=location)
            return await NonDiscordRidesRepository.create_ride(session, ride)
        except IntegrityError:
            raise DuplicateRideError(f"Pickup for {name} on {ride_date} already exists.")  # noqa: B904

    async def remove_pickup(self, name: str, day: str, session: AsyncSession | None = None) -> bool:
        """
        Removes a pickup for a non-Discord user.

        Args:
            name: Name of the person.
            day: Day of the pickup.
            session: Optional database session. If None, one is created internally.

        Returns:
            True if the pickup was removed, False if not found.
        """
        ride_date = get_next_date_obj(day)
        if session is not None:
            return await self._remove_pickup(session, name, ride_date)

        async with AsyncSessionLocal() as session:
            return await self._remove_pickup(session, name, ride_date)

    async def _remove_pickup(self, session: AsyncSession, name: str, ride_date: date) -> bool:
        ride = await NonDiscordRidesRepository.get_ride(session, name, ride_date)
        if ride:
            await NonDiscordRidesRepository.delete_ride(session, ride)
            return True
        return False

    async def list_pickups(
        self, day: str, session: AsyncSession | None = None
    ) -> list[NonDiscordRides]:
        """
        Lists all pickups for a specific day.

        Args:
            day: The day to list pickups for.
            session: Optional database session. If None, one is created internally.

        Returns:
            A list of NonDiscordRides objects.
        """
        ride_date = get_next_date_obj(day)
        if session is not None:
            return await NonDiscordRidesRepository.get_rides_by_date(session, ride_date)

        async with AsyncSessionLocal() as session:
            return await NonDiscordRidesRepository.get_rides_by_date(session, ride_date)

    async def delete_past_pickups(self, session: AsyncSession | None = None) -> int:
        """
        Deletes all pickups from past dates.

        Args:
            session: Optional database session. If None, one is created internally.

        Returns:
            The number of deleted pickups.
        """
        today = date.today()
        if session is not None:
            return await NonDiscordRidesRepository.delete_past_rides(session, today)

        async with AsyncSessionLocal() as session:
            return await NonDiscordRidesRepository.delete_past_rides(session, today)
