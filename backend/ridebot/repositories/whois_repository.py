"""Repository for whois data access."""

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import DiscordUsers
from bot.core.models import Locations as LocationsModel

logger = logging.getLogger(__name__)


class WhoisRepository:
    """Handles database operations for whois lookups."""

    @staticmethod
    async def get_display_name(session: AsyncSession, discord_username: str) -> str | None:
        """
        Look up a user's full name from the discord_usernames table.

        Args:
            session: An active async database session.
            discord_username: The Discord username to look up.

        Returns:
            "first_name last_name" (stripped) if found, otherwise None.
        """
        try:
            stmt = select(DiscordUsers).where(DiscordUsers.discord_username == discord_username)
            result = await session.execute(stmt)
            user = result.scalars().first()
            if user:
                return f"{user.first_name} {user.last_name}".strip()
            return None
        except Exception:
            logger.exception("Failed to get display name for %s", discord_username)
            return None

    @staticmethod
    async def fetch_data_by_name(session: AsyncSession, name: str) -> list[Row]:
        """
        Fetches 'name' and 'discord_username' from the database based on a partial match.

        The search is case-insensitive and checks against both the 'name' and
        'discord_username' columns in the Locations model.

        Args:
            session: The SQLAlchemy AsyncSession object for database interaction.
            name: The partial name or Discord username string to search for.

        Returns:
            A list of SQLAlchemy Row objects, where each row contains
            (LocationsModel.name, LocationsModel.discord_username).
            Returns an empty list if no matches are found.
        """
        stmt = select(LocationsModel.name, LocationsModel.discord_username).where(
            or_(
                func.lower(LocationsModel.name).contains(name.lower()),
                func.lower(LocationsModel.discord_username).contains(name.lower()),
            )
        )
        result = await session.execute(stmt)
        return list(result.all())
