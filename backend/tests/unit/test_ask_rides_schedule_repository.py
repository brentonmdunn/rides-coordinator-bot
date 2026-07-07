"""Unit tests for AskRidesScheduleRepository (data access layer)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import AskRidesScheduleSlot
from bot.repositories.ask_rides_schedule_repository import AskRidesScheduleRepository


def _make_session(scalars_first=None, scalars_all=None):
    """Build a mock AsyncSession with configurable execute results."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.one_or_none.return_value = scalars_first
    result.scalars.return_value.all.return_value = scalars_all or []
    session.execute = AsyncMock(return_value=result)
    return session


def _make_schedule_row(
    slot=AskRidesScheduleSlot.WEDNESDAY_REMINDER, day_of_week=0, hour=11, minute=0
):
    row = MagicMock()
    row.slot = slot
    row.day_of_week = day_of_week
    row.hour = hour
    row.minute = minute
    return row


@pytest.mark.asyncio
async def test_get_returns_row_when_found():
    row = _make_schedule_row()
    session = _make_session(scalars_first=row)

    result = await AskRidesScheduleRepository.get(session, AskRidesScheduleSlot.WEDNESDAY_REMINDER)

    session.execute.assert_awaited_once()
    assert result is row


@pytest.mark.asyncio
async def test_get_returns_none_when_missing():
    session = _make_session(scalars_first=None)

    result = await AskRidesScheduleRepository.get(session, AskRidesScheduleSlot.FRI_SUN_GROUP)

    assert result is None


@pytest.mark.asyncio
async def test_get_all_returns_all_rows():
    rows = [_make_schedule_row(), _make_schedule_row(slot=AskRidesScheduleSlot.FRI_SUN_GROUP)]
    session = _make_session(scalars_all=rows)

    result = await AskRidesScheduleRepository.get_all(session)

    assert result == rows


@pytest.mark.asyncio
async def test_upsert_reads_back_row():
    row = _make_schedule_row(day_of_week=1, hour=10, minute=30)
    session = _make_session(scalars_first=row)

    result = await AskRidesScheduleRepository.upsert(
        session,
        AskRidesScheduleSlot.WEDNESDAY_REMINDER,
        day_of_week=1,
        hour=10,
        minute=30,
        updated_by="editor@example.com",
    )

    assert result is row
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_raises_if_readback_missing():
    session = _make_session(scalars_first=None)

    with pytest.raises(RuntimeError, match="Failed to read back"):
        await AskRidesScheduleRepository.upsert(
            session,
            AskRidesScheduleSlot.WEDNESDAY_REMINDER,
            day_of_week=1,
            hour=10,
            minute=30,
            updated_by="editor@example.com",
        )


@pytest.mark.asyncio
async def test_delete_executes_and_commits():
    session = _make_session()

    await AskRidesScheduleRepository.delete(session, AskRidesScheduleSlot.FRI_SUN_GROUP)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
