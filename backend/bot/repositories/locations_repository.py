"""Repository for location data access."""

from sqlalchemy import delete, func, or_, select

from bot.core.database import AsyncSessionLocal
from bot.core.logger import logger
from bot.core.models import Locations as LocationsModel
from bot.core.models import NonDiscordRides
from bot.utils.time_helpers import get_next_date_obj


class LocationsRepository:
    """Handles database operations for locations."""

    async def get_non_discord_pickups(self, day):
        """Retrieves non-Discord pickups for a specific day.

        Args:
            day: The day to filter by.

        Returns:
            A list of NonDiscordRides objects.
        """
        date_to_list = get_next_date_obj(day.title())
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(NonDiscordRides).where(NonDiscordRides.date == date_to_list)
                result = await session.execute(stmt)
                pickups = result.scalars().all()
                return pickups or []
            except Exception:
                logger.exception("An error occurred while listing pickups")
                return []

    async def get_location_check_discord(self, session, name):
        """Checks for location based on Discord username.

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

    async def get_location_check_name_and_discord(self, session, name):
        """Checks for location based on name or Discord username.

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

    async def get_discord_username(self, session, name: str) -> str | None:
        """Retrieves the Discord username for a given name.

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

    async def get_name(self, session, discord_username: str) -> str | None:
        """Retrieves the name for a given Discord username.

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

    async def get_name_location(self, session, discord_username: str) -> tuple[str, str] | None:
        """Retrieves name and location for a Discord username.

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

    async def sync_locations(self, session, locations_to_add: list[LocationsModel]):
        """Syncs the locations table with new data.

        Args:
            session: The database session.
            locations_to_add: List of LocationsModel objects to add.
        """
        await session.execute(delete(LocationsModel))
        if locations_to_add:
            session.add_all(locations_to_add)
        await session.commit()
