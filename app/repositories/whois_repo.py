from sqlalchemy import func, or_, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import Locations as LocationsModel


class WhoisRepo:
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
        return result.all()
