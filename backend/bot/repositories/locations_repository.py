"""Repository for location data access."""

import logging

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import Locations as LocationsModel
from bot.core.models import NonDiscordRides
from bot.utils.time_helpers import get_next_date_obj

logger = logging.getLogger(__name__)


class LocationsRepository:
    """Handles database operations for locations."""

    @staticmethod
    async def get_non_discord_pickups(session: AsyncSession, day):
        """
        Retrieves non-Discord pickups for a specific day.

        Args:
            session: The database session.
            day: The day to filter by.

        Returns:
            A list of NonDiscordRides objects.
        """
        date_to_list = get_next_date_obj(day.title())
        try:
            stmt = select(NonDiscordRides).where(NonDiscordRides.date == date_to_list)
            result = await session.execute(stmt)
            pickups = result.scalars().all()
            return pickups or []
        except Exception:
            logger.exception("An error occurred while listing pickups")
            return []

    @staticmethod
    async def get_location_check_discord(session: AsyncSession, name):
        """
        Checks for location based on Discord username.

        Args:
            session: The database session.
            name: The name to search for.

        Returns:
            A list of matching location records.
        """
        stmt = select(LocationsModel.name, LocationsModel.location).where(
            or_(
                func.lower(LocationsModel.discord_username).contains(name.lower()),
            )
        )
        result = await session.execute(stmt)
        possible_people = result.all()
        return possible_people

    @staticmethod
    async def get_location_check_name_and_discord(session: AsyncSession, name):
        """
        Checks for location based on name or Discord username.

        Args:
            session: The database session.
            name: The name to search for.

        Returns:
            A list of matching location records.
        """
        stmt = select(LocationsModel.name, LocationsModel.location).where(
            or_(
                func.lower(LocationsModel.name).contains(name.lower()),
                func.lower(LocationsModel.discord_username).contains(name.lower()),
            )
        )
        result = await session.execute(stmt)
        possible_people = result.all()
        return possible_people

    @staticmethod
    async def get_discord_username(session: AsyncSession, name: str) -> str | None:
        """
        Retrieves the Discord username for a given name.

        Args:
            session: The database session.
            name: The name to search for.

        Returns:
            The Discord username if found, otherwise None.
        """
        stmt = select(LocationsModel.discord_username).where(
            func.lower(LocationsModel.name) == name.lower()
        )
        result = await session.execute(stmt)
        discord_username = result.scalars().first()
        return discord_username

    @staticmethod
    async def get_name(session: AsyncSession, discord_username: str) -> str | None:
        """
        Retrieves the name for a given Discord username.

        Args:
            session: The database session.
            discord_username: The Discord username to search for.

        Returns:
            The name if found, otherwise None.
        """
        stmt = select(LocationsModel.name).where(
            func.lower(LocationsModel.discord_username) == discord_username.lower()
        )
        result = await session.execute(stmt)
        name = result.scalars().first()
        return name

    @staticmethod
    async def get_names_for_usernames(
        session: AsyncSession, discord_usernames: set[str]
    ) -> dict[str, str]:
        """
        Retrieves names for multiple Discord usernames in a batch.

        Args:
            session: The database session.
            discord_usernames: Set of Discord usernames to look up.

        Returns:
            Dictionary mapping Discord usernames to their actual names.
            Only includes usernames that have a matching record.
        """
        if not discord_usernames:
            return {}

        lowercase_usernames = {username.lower() for username in discord_usernames}

        stmt = select(LocationsModel.discord_username, LocationsModel.name).where(
            func.lower(LocationsModel.discord_username).in_(lowercase_usernames)
        )
        result = await session.execute(stmt)
        rows = result.all()

        username_to_name = {}
        for db_username, name in rows:
            for original_username in discord_usernames:
                if original_username.lower() == db_username.lower():
                    username_to_name[original_username] = name
                    break

        return username_to_name

    @staticmethod
    async def get_name_location(
        session: AsyncSession, discord_username: str
    ) -> tuple[str, str] | None:
        """
        Retrieves name and location for a Discord username.

        Args:
            session: The database session.
            discord_username: The Discord username to search for.

        Returns:
            A tuple containing (name, location) if found, otherwise None.
        """
        stmt = select(LocationsModel.name, LocationsModel.location).where(
            func.lower(LocationsModel.discord_username) == str(discord_username).lower()
        )
        result = await session.execute(stmt)
        person = result.first()
        return person

    @staticmethod
    async def get_all_discord_usernames(session: AsyncSession) -> list[tuple[str, str]]:
        """Return (discord_username, name) pairs for all rows with a non-null username."""
        stmt = select(LocationsModel.discord_username, LocationsModel.name).where(
            LocationsModel.discord_username.is_not(None)
        )
        result = await session.execute(stmt)
        return [(username, name) for username, name in result.all()]

    @staticmethod
    async def sync_locations(session: AsyncSession, locations_to_add: list[LocationsModel]):
        """
        Syncs the locations table with new data.

        Args:
            session: The database session.
            locations_to_add: List of LocationsModel objects to add.
        """
        await session.execute(delete(LocationsModel))
        if locations_to_add:
            session.add_all(locations_to_add)
        await session.commit()
