# app/repositories/locations_repository.py

from sqlalchemy import delete, func, or_, select

from app.core.database import AsyncSessionLocal
from app.core.logger import logger
from app.core.models import Locations as LocationsModel
from app.core.models import NonDiscordRides
from app.utils.time_helpers import get_next_date_obj


class LocationsRepository:
    async def get_non_discord_pickups(self, day):
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
        stmt = select(LocationsModel.name, LocationsModel.location).where(
            or_(
                func.lower(LocationsModel.discord_username).contains(name.lower()),
            )
        )
        result = await session.execute(stmt)
        possible_people = result.all()
        return possible_people

    async def get_location_check_name_and_discord(self, session, name):
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
        stmt = select(LocationsModel.discord_username).where(
            func.lower(LocationsModel.name) == name.lower()
        )
        result = await session.execute(stmt)
        discord_username = result.scalars().first()
        return discord_username

    async def get_name(self, session, discord_username: str) -> str | None:
        stmt = select(LocationsModel.name).where(
            func.lower(LocationsModel.discord_username) == discord_username.lower()
        )
        result = await session.execute(stmt)
        name = result.scalars().first()
        return name

    async def get_name_location(self, session, discord_username: str) -> tuple[str, str] | None:
        stmt = select(LocationsModel.name, LocationsModel.location).where(
            func.lower(LocationsModel.discord_username) == str(discord_username).lower()
        )
        result = await session.execute(stmt)
        person = result.first()
        return person

    async def sync_locations(self, session, locations_to_add: list[LocationsModel]):
        await session.execute(delete(LocationsModel))
        if locations_to_add:
            session.add_all(locations_to_add)
        await session.commit()
