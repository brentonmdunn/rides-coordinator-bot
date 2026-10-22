"""Repository for non-Discord rides data access."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ridebot.repositories.ride_events_repository import RideEventsRepository
from ridebot.utils.constants import GUILD_ID
from shared.core.enums import AskRidesMessageType, Emoji
from shared.core.models import NonDiscordRides, RideRequest


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
        await NonDiscordRidesRepository.sync_request(session, ride)
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
        await NonDiscordRidesRepository.sync_request(session, ride, active=False)
        await session.commit()

    @staticmethod
    async def sync_request(session, ride, *, active=True):
        """Keep the legacy coordinator API and canonical event participant in one transaction."""
        kind = {
            2: AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
            4: AskRidesMessageType.FRIDAY_FELLOWSHIP,
            6: AskRidesMessageType.SUNDAY_SERVICE,
        }.get(ride.date.weekday())
        if kind is None:
            return
        if ride.emoji == Emoji.SUNDAY_CLASS:
            kind = AskRidesMessageType.SUNDAY_CLASS
        event = await RideEventsRepository.ensure_event(
            session, guild_id=str(GUILD_ID), message_type=str(kind), event_date=ride.date
        )
        key = f"non_discord:{ride.name}"
        requests = await RideEventsRepository.requests(session, event.id, active_only=False)
        row = next((r for r in requests if r.identity_key == key), None)
        if row is None:
            row = RideRequest(
                event_id=event.id, identity_key=key, source="non_discord", discord_user_id=None
            )
            session.add(row)
        row.name, row.location, row.active, row.pickup = ride.name, ride.location, active, True
        row.return_preference = (
            "lunch"
            if ride.emoji == Emoji.LUNCH
            else ("home" if ride.emoji in {Emoji.NO_LUNCH, Emoji.FRIDAY_FELLOWSHIP} else "unknown")
        )
        row.needs_review = ride.emoji == Emoji.SOMETHING_ELSE
        row.updated_at = datetime.now(UTC).replace(tzinfo=None)
        if not active:
            for assignment in await RideEventsRepository.assignments(session, event.id):
                if assignment.request_id == row.id:
                    await session.delete(assignment)

    @staticmethod
    async def import_requests(session, since):
        """Idempotently import existing dated non-Discord rows during rollout/reconciliation."""
        rides = list(
            (
                await session.scalars(select(NonDiscordRides).where(NonDiscordRides.date >= since))
            ).all()
        )
        for ride in rides:
            await NonDiscordRidesRepository.sync_request(session, ride)
        return len(rides)

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
