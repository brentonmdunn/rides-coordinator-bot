"""Data access layer for editable scheduled pickup-summary settings."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.core.enums import PickupSummarySlot
from shared.core.models import PickupSummarySetting


class PickupSummarySettingsRepository:
    """Handles database operations for pickup-summary settings."""

    @staticmethod
    async def get_all(session: AsyncSession) -> list[PickupSummarySetting]:
        """Return all saved pickup-summary setting rows."""
        stmt = select(PickupSummarySetting)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get(session: AsyncSession, slot: PickupSummarySlot) -> PickupSummarySetting | None:
        """Return the saved setting row for a slot, or None if not customized."""
        stmt = select(PickupSummarySetting).where(PickupSummarySetting.slot == slot)
        result = await session.execute(stmt)
        return result.scalars().one_or_none()

    @staticmethod
    async def upsert(
        session: AsyncSession,
        slot: PickupSummarySlot,
        enabled: bool,
        day_of_week: int,
        hour: int,
        minute: int,
        updated_by: str,
    ) -> PickupSummarySetting:
        """Insert or update the setting row for a slot."""
        stmt = insert(PickupSummarySetting).values(
            slot=slot,
            enabled=enabled,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            updated_by=updated_by,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PickupSummarySetting.slot],
            set_={
                "enabled": enabled,
                "day_of_week": day_of_week,
                "hour": hour,
                "minute": minute,
                "updated_by": updated_by,
            },
        )
        await session.execute(stmt)
        await session.commit()

        result = await PickupSummarySettingsRepository.get(session, slot)
        if result is None:
            # Should never happen — the row was just upserted above.
            raise RuntimeError(f"Failed to read back upserted pickup summary setting for {slot}")
        return result

    @staticmethod
    async def delete(session: AsyncSession, slot: PickupSummarySlot) -> None:
        """Delete the saved setting row for a slot (reset to default). No-op if absent."""
        stmt = delete(PickupSummarySetting).where(PickupSummarySetting.slot == slot)
        await session.execute(stmt)
        await session.commit()
