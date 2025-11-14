# app/features/locations/locations_repository.py

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logger import logger
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
