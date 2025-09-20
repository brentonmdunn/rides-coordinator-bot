import datetime

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logger import logger
from app.core.models import NonDiscordRides


async def delete_past_pickups():
    """
    Deletes all records from the NonDiscordRides table
    where the date is earlier than the current date.
    """
    today = datetime.date.today()

    async with AsyncSessionLocal() as session:
        try:
            # First, find the records to be deleted.
            stmt = select(NonDiscordRides).where(NonDiscordRides.date < today)
            result = await session.execute(stmt)
            records_to_delete = result.scalars().all()

            if records_to_delete:
                for record in records_to_delete:
                    await session.delete(record)
                await session.commit()
                # You can add logging here to confirm deletion
                logger.info(f"Successfully deleted {len(records_to_delete)} past pickup entries.")
            else:
                logger.info("No past pickup entries found to delete.")

        except Exception as e:
            await session.rollback()
            logger.error(f"An error occurred while deleting past pickups: {e}")
