"""Unit tests for TempDriverGrantsRepository (data access layer)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ridebot.repositories.temp_driver_grants_repository import TempDriverGrantsRepository


def _make_session(scalars_first=None, scalars_all=None, rowcount=1):
    """Build a mock AsyncSession with configurable execute results."""
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.one_or_none.return_value = scalars_first
    result.scalars.return_value.all.return_value = scalars_all or []
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)
    return session


def _make_grant_row(discord_user_id="123", expires_at=None):
    from unittest.mock import MagicMock

    row = MagicMock()
    row.discord_user_id = discord_user_id
    row.discord_username = "alice"
    row.expires_at = expires_at or datetime(2026, 1, 1)
    row.granted_by = "coordinator"
    return row


@pytest.mark.asyncio
async def test_upsert_executes_without_committing():
    session = _make_session()

    await TempDriverGrantsRepository.upsert(
        session,
        discord_user_id="123",
        discord_username="alice",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        granted_by="coordinator",
    )

    session.execute.assert_awaited_once()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_strips_tzinfo_before_storing():
    session = _make_session()

    await TempDriverGrantsRepository.upsert(
        session,
        discord_user_id="123",
        discord_username="alice",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        granted_by="coordinator",
    )

    stmt = session.execute.call_args[0][0]
    compiled_values = stmt.compile().params
    assert compiled_values["expires_at"].tzinfo is None


@pytest.mark.asyncio
async def test_get_returns_row_when_found():
    row = _make_grant_row()
    session = _make_session(scalars_first=row)

    result = await TempDriverGrantsRepository.get(session, "123")

    assert result is row


@pytest.mark.asyncio
async def test_get_returns_none_when_missing():
    session = _make_session(scalars_first=None)

    result = await TempDriverGrantsRepository.get(session, "999")

    assert result is None


@pytest.mark.asyncio
async def test_list_all_returns_all_rows_ordered():
    rows = [_make_grant_row("1"), _make_grant_row("2")]
    session = _make_session(scalars_all=rows)

    result = await TempDriverGrantsRepository.list_all(session)

    assert result == rows


@pytest.mark.asyncio
async def test_list_expired_filters_by_now():
    rows = [_make_grant_row("1")]
    session = _make_session(scalars_all=rows)

    result = await TempDriverGrantsRepository.list_expired(
        session, datetime(2026, 1, 2, tzinfo=UTC)
    )

    session.execute.assert_awaited_once()
    assert result == rows


@pytest.mark.asyncio
async def test_delete_returns_true_when_row_existed():
    session = _make_session(rowcount=1)

    result = await TempDriverGrantsRepository.delete(session, "123")

    assert result is True
    session.execute.assert_awaited_once()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_returns_false_when_no_row():
    session = _make_session(rowcount=0)

    result = await TempDriverGrantsRepository.delete(session, "999")

    assert result is False
