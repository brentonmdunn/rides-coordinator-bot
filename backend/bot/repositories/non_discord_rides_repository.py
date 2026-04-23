"""Repository for non-Discord rides data access."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import NonDiscordRides


class NonDiscordRidesRepository:
    """Handles database operations for non-Discord rides."""

    @staticmethod
    async def create_ride(session: AsyncSession, ride: NonDiscordRides) -> NonDiscordRides:
        """
        Creates a new non-Discord ride.

        Args:
            session: The database session.
            ride: The NonDiscordRides object to create.

        Returns:
            The created NonDiscordRides object.
        """
        session.add(ride)
        await session.commit()
        return ride

    @staticmethod
    async def get_ride(session: AsyncSession, name: str, ride_date: date) -> NonDiscordRides | None:
        """
        Retrieves a ride by name and date.

        Args:
            session: The database session.
            name: The name of the person.
            ride_date: The date of the ride.

        Returns:
            The NonDiscordRides object if found, otherwise None.
        """
        stmt = select(NonDiscordRides).where(
            NonDiscordRides.name == name, NonDiscordRides.date == ride_date
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_ride(session: AsyncSession, ride: NonDiscordRides) -> None:
        """
        Deletes a ride.

        Args:
            session: The database session.
            ride: The NonDiscordRides object to delete.
        """
        await session.delete(ride)
        await session.commit()

    @staticmethod
    async def get_rides_by_date(session: AsyncSession, ride_date: date) -> list[NonDiscordRides]:
        """
        Retrieves all rides for a specific date.

        Args:
            session: The database session.
            ride_date: The date to filter by.

        Returns:
            A list of NonDiscordRides objects.
        """
        stmt = select(NonDiscordRides).where(NonDiscordRides.date == ride_date)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_past_rides(session: AsyncSession, date_limit: date) -> int:
        """
        Deletes rides before a specific date.

        Args:
            session: The database session.
            date_limit: The date limit.

        Returns:
            The number of deleted rides.
        """
        stmt = select(NonDiscordRides).where(NonDiscordRides.date < date_limit)
        result = await session.execute(stmt)
        records_to_delete = result.scalars().all()

        for record in records_to_delete:
            await session.delete(record)

        await session.commit()
        return len(records_to_delete)
