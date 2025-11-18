# app/repositories/locations_repository.py

from sqlalchemy import func, or_, select

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
