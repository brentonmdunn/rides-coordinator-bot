"""Data access layer for editable ask-rides send schedule slots."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import AskRidesScheduleSlot
from bot.core.models import AskRidesSchedule


class AskRidesScheduleRepository:
    """Handles database operations for ask-rides schedule slots."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[AskRidesSchedule]:
        """Return all saved schedule rows."""
        stmt = select(AskRidesSchedule)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, slot: AskRidesScheduleSlot) -> AskRidesSchedule | None:
        """Return the saved schedule row for a slot, or None if not customized."""
        stmt = select(AskRidesSchedule).where(AskRidesSchedule.slot == slot)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @staticmethod
    async def upsert(
        session: AsyncSession,
        slot: AskRidesScheduleSlot,
        day_of_week: int,
        hour: int,
        minute: int,
        updated_by: str,
    ) -> AskRidesSchedule:
        """Insert or update the schedule row for a slot."""
        stmt = insert(AskRidesSchedule).values(
            slot=slot,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            updated_by=updated_by,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[AskRidesSchedule.slot],
            set_={
                "day_of_week": day_of_week,
                "hour": hour,
                "minute": minute,
                "updated_by": updated_by,
            },
        )
        await session.execute(stmt)
        await session.commit()

        result = await AskRidesScheduleRepository.get(session, slot)
        if result is None:
            # Should never happen — the row was just upserted above.
            raise RuntimeError(f"Failed to read back upserted schedule for {slot}")
        return result

    @staticmethod
    async def delete(session: AsyncSession, slot: AskRidesScheduleSlot) -> None:
        """Delete the saved schedule row for a slot (reset to default)."""
        stmt = delete(AskRidesSchedule).where(AskRidesSchedule.slot == slot)
        await session.execute(stmt)
        await session.commit()
