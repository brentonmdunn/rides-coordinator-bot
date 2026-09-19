"""Unit tests for PickupSummarySettingsRepository (data access layer)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ridebot.repositories.pickup_summary_settings_repository import (
    PickupSummarySettingsRepository,
)
from shared.core.enums import PickupSummarySlot


def _make_session(scalars_first=None, scalars_all=None):
    """Build a mock AsyncSession with configurable execute results."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.one_or_none.return_value = scalars_first
    result.scalars.return_value.all.return_value = scalars_all or []
    session.execute = AsyncMock(return_value=result)
    return session


def _make_setting_row(
    slot=PickupSummarySlot.FRIDAY, enabled=True, day_of_week=4, hour=11, minute=0
):
    row = MagicMock()
    row.slot = slot
    row.enabled = enabled
    row.day_of_week = day_of_week
    row.hour = hour
    row.minute = minute
    return row


@pytest.mark.asyncio
async def test_get_returns_row_when_found():
    row = _make_setting_row()
    session = _make_session(scalars_first=row)

    result = await PickupSummarySettingsRepository.get(session, PickupSummarySlot.FRIDAY)

    session.execute.assert_awaited_once()
    assert result is row


@pytest.mark.asyncio
async def test_get_returns_none_when_missing():
    session = _make_session(scalars_first=None)

    result = await PickupSummarySettingsRepository.get(session, PickupSummarySlot.SUNDAY)

    assert result is None


@pytest.mark.asyncio
async def test_get_all_returns_all_rows():
    rows = [_make_setting_row(), _make_setting_row(slot=PickupSummarySlot.SUNDAY)]
    session = _make_session(scalars_all=rows)

    result = await PickupSummarySettingsRepository.get_all(session)

    assert result == rows


@pytest.mark.asyncio
async def test_upsert_reads_back_row():
    row = _make_setting_row(enabled=False, day_of_week=1, hour=10, minute=30)
    session = _make_session(scalars_first=row)

    result = await PickupSummarySettingsRepository.upsert(
        session,
        PickupSummarySlot.FRIDAY,
        enabled=False,
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
        await PickupSummarySettingsRepository.upsert(
            session,
            PickupSummarySlot.FRIDAY,
            enabled=True,
            day_of_week=1,
            hour=10,
            minute=30,
            updated_by="editor@example.com",
        )


@pytest.mark.asyncio
async def test_delete_executes_and_commits():
    session = _make_session()

    await PickupSummarySettingsRepository.delete(session, PickupSummarySlot.SUNDAY)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
