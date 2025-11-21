from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import NonDiscordRides


class NonDiscordRidesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_ride(self, ride: NonDiscordRides) -> NonDiscordRides:
        self.session.add(ride)
        await self.session.commit()
        return ride

    async def get_ride(self, name: str, ride_date: date) -> NonDiscordRides | None:
        stmt = select(NonDiscordRides).where(
            NonDiscordRides.name == name, NonDiscordRides.date == ride_date
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_ride(self, ride: NonDiscordRides) -> None:
        await self.session.delete(ride)
        await self.session.commit()

    async def get_rides_by_date(self, ride_date: date) -> list[NonDiscordRides]:
        stmt = select(NonDiscordRides).where(NonDiscordRides.date == ride_date)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_past_rides(self, date_limit: date) -> int:
        stmt = select(NonDiscordRides).where(NonDiscordRides.date < date_limit)
        result = await self.session.execute(stmt)
        records_to_delete = result.scalars().all()

        for record in records_to_delete:
            await self.session.delete(record)
        
        await self.session.commit()
        return len(records_to_delete)
