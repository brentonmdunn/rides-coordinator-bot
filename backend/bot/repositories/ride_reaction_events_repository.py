"""Repository for ride reaction event data access."""

import datetime
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import RideReactionEvent

logger = logging.getLogger(__name__)


class RideReactionEventsRepository:
    """Handles database operations for ride reaction events."""

    @staticmethod
    async def record_event(
        session: AsyncSession,
        message_id: str,
        discord_username: str,
        display_name: str | None,
        emoji: str,
        action: str,
        occurred_at: datetime.datetime,
        ride_date: datetime.date | None,
        ride_type: str | None,
    ) -> None:
        try:
            entry = RideReactionEvent(
                message_id=message_id,
                discord_username=discord_username,
                display_name=display_name,
                emoji=emoji,
                action=action,
                occurred_at=occurred_at,
                ride_date=ride_date,
                ride_type=ride_type,
            )
            session.add(entry)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    @staticmethod
    async def get_events(
        session: AsyncSession,
        ride_type: str | None = None,
        date_from: datetime.date | None = None,
        date_to: datetime.date | None = None,
        emoji: str | None = None,
    ) -> list[RideReactionEvent]:
        try:
            stmt = select(RideReactionEvent)
            if ride_type:
                stmt = stmt.where(RideReactionEvent.ride_type == ride_type)
            if date_from:
                stmt = stmt.where(RideReactionEvent.ride_date >= date_from)
            if date_to:
                stmt = stmt.where(RideReactionEvent.ride_date <= date_to)
            if emoji:
                stmt = stmt.where(RideReactionEvent.emoji == emoji)
            stmt = stmt.order_by(RideReactionEvent.occurred_at.asc())
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get ride reaction events")
            return []
