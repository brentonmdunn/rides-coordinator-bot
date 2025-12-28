"""Repository for non-Discord rides data access."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import NonDiscordRides


class NonDiscordRidesRepository:
    """Handles database operations for non-Discord rides."""

    def __init__(self, session: AsyncSession):
        """Initialize the NonDiscordRidesRepository."""

        self.session = session

    async def create_ride(self, ride: NonDiscordRides) -> NonDiscordRides:
        """Creates a new non-Discord ride.

        Args:
            ride: The NonDiscordRides object to create.

        Returns:
            The created NonDiscordRides object.
        """
        self.session.add(ride)
        await self.session.commit()
        return ride

    async def get_ride(self, name: str, ride_date: date) -> NonDiscordRides | None:
        """Retrieves a ride by name and date.

        Args:
            name: The name of the person.
            ride_date: The date of the ride.

        Returns:
            The NonDiscordRides object if found, otherwise None.
        """
        stmt = select(NonDiscordRides).where(
            NonDiscordRides.name == name, NonDiscordRides.date == ride_date
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_ride(self, ride: NonDiscordRides) -> None:
        """Deletes a ride.

        Args:
            ride: The NonDiscordRides object to delete.
        """
        await self.session.delete(ride)
        await self.session.commit()

    async def get_rides_by_date(self, ride_date: date) -> list[NonDiscordRides]:
        """Retrieves all rides for a specific date.

        Args:
            ride_date: The date to filter by.

        Returns:
            A list of NonDiscordRides objects.
        """
        stmt = select(NonDiscordRides).where(NonDiscordRides.date == ride_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_past_rides(self, date_limit: date) -> int:
        """Deletes rides before a specific date.

        Args:
            date_limit: The date limit.

        Returns:
            The number of deleted rides.
        """
        stmt = select(NonDiscordRides).where(NonDiscordRides.date < date_limit)
        result = await self.session.execute(stmt)
        records_to_delete = result.scalars().all()

        for record in records_to_delete:
            await self.session.delete(record)

        await self.session.commit()
        return len(records_to_delete)
