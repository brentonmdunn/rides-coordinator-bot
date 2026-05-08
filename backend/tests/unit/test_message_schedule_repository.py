"""Unit tests for MessageScheduleRepository (data access layer)."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import JobName
from bot.repositories.message_schedule_repository import MessageScheduleRepository


def _make_session(scalars_first=None, scalars_all=None, rowcount=0):
    """Build a mock AsyncSession with configurable execute results."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.first.return_value = scalars_first
    result.scalars.return_value.all.return_value = scalars_all or []
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)
    return session


def _make_pause(job_name=JobName.FRIDAY, is_paused=False, resume_after_date=None):
    """Build a minimal mock MessageSchedulePause."""
    pause = MagicMock()
    pause.job_name = job_name
    pause.is_paused = is_paused
    pause.resume_after_date = resume_after_date
    return pause


# ---------------------------------------------------------------------------
# get_pause_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pause_status_found():
    """Should return the pause row when found."""
    mock_pause = _make_pause(job_name=JobName.FRIDAY)
    session = _make_session(scalars_first=mock_pause)

    result = await MessageScheduleRepository.get_pause_status(session, JobName.FRIDAY)

    session.execute.assert_awaited_once()
    assert result is mock_pause


@pytest.mark.asyncio
async def test_get_pause_status_not_found():
    """Should return None when no row exists for the job."""
    session = _make_session(scalars_first=None)

    result = await MessageScheduleRepository.get_pause_status(session, JobName.SUNDAY)

    assert result is None


# ---------------------------------------------------------------------------
# get_all_pause_statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_pause_statuses_returns_list():
    """Should return all pause rows."""
    pauses = [_make_pause(JobName.FRIDAY), _make_pause(JobName.SUNDAY)]
    session = _make_session(scalars_all=pauses)

    result = await MessageScheduleRepository.get_all_pause_statuses(session)

    session.execute.assert_awaited_once()
    assert result == pauses


@pytest.mark.asyncio
async def test_get_all_pause_statuses_empty():
    """Should return an empty list when no rows exist."""
    session = _make_session(scalars_all=[])

    result = await MessageScheduleRepository.get_all_pause_statuses(session)

    assert result == []


# ---------------------------------------------------------------------------
# set_pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_pause_updates_and_returns_row():
    """Should execute update, commit, then fetch and return the updated row."""
    mock_pause = _make_pause(job_name=JobName.FRIDAY, is_paused=True)

    # First execute call (update) returns rowcount=1
    # Second execute call (select) returns the pause row
    update_result = MagicMock()
    update_result.rowcount = 1

    fetch_result = MagicMock()
    fetch_result.scalars.return_value.first.return_value = mock_pause

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[update_result, fetch_result])

    result = await MessageScheduleRepository.set_pause(
        session,
        job_name=JobName.FRIDAY,
        is_paused=True,
        resume_after_date=None,
    )

    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()
    assert result is mock_pause


@pytest.mark.asyncio
async def test_set_pause_returns_none_when_row_not_found():
    """Should return None and log a warning when no row matches the job name."""
    update_result = MagicMock()
    update_result.rowcount = 0

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=update_result)

    result = await MessageScheduleRepository.set_pause(
        session,
        job_name="nonexistent_job",
        is_paused=True,
    )

    session.commit.assert_awaited_once()
    assert result is None


@pytest.mark.asyncio
async def test_set_pause_with_resume_date():
    """Should pass resume_after_date through to the update values."""
    mock_pause = _make_pause(
        job_name=JobName.SUNDAY,
        is_paused=True,
        resume_after_date=datetime.date(2026, 6, 1),
    )

    update_result = MagicMock()
    update_result.rowcount = 1

    fetch_result = MagicMock()
    fetch_result.scalars.return_value.first.return_value = mock_pause

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[update_result, fetch_result])

    result = await MessageScheduleRepository.set_pause(
        session,
        job_name=JobName.SUNDAY,
        is_paused=True,
        resume_after_date=datetime.date(2026, 6, 1),
    )

    assert result is mock_pause


# ---------------------------------------------------------------------------
# clear_pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_pause_executes_and_commits():
    """Should execute an update statement and commit."""
    session = _make_session()

    await MessageScheduleRepository.clear_pause(session, JobName.FRIDAY)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# is_job_paused
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_job_paused_no_row_returns_false():
    """Should return False when there is no pause row."""
    session = _make_session(scalars_first=None)

    result = await MessageScheduleRepository.is_job_paused(session, JobName.FRIDAY)

    assert result is False


@pytest.mark.asyncio
async def test_is_job_paused_not_paused_returns_false():
    """Should return False when the row exists but is_paused=False."""
    pause = _make_pause(is_paused=False)
    session = _make_session(scalars_first=pause)

    result = await MessageScheduleRepository.is_job_paused(session, JobName.FRIDAY)

    assert result is False


@pytest.mark.asyncio
async def test_is_job_paused_indefinite_returns_true():
    """Should return True when is_paused=True and resume_after_date is None."""
    pause = _make_pause(is_paused=True, resume_after_date=None)
    session = _make_session(scalars_first=pause)

    result = await MessageScheduleRepository.is_job_paused(session, JobName.FRIDAY)

    assert result is True


@pytest.mark.asyncio
async def test_is_job_paused_date_in_future_returns_true():
    """Should return True when is_paused=True and send Wednesday is in the future."""
    # Use a date far in the future so today < send_wednesday
    future_date = datetime.date(2099, 12, 31)
    pause = _make_pause(is_paused=True, resume_after_date=future_date)
    session = _make_session(scalars_first=pause)

    result = await MessageScheduleRepository.is_job_paused(session, JobName.FRIDAY)

    assert result is True


@pytest.mark.asyncio
async def test_is_job_paused_date_reached_auto_clears():
    """Should auto-clear the pause and return False when send Wednesday has passed."""
    # A date in the past so get_send_wednesday returns a past date
    past_date = datetime.date(2020, 1, 5)  # A Sunday — send Wednesday would be 2020-01-01
    pause = _make_pause(is_paused=True, resume_after_date=past_date)

    # First execute: the select to get the pause row
    # Second execute: the update to auto-clear
    select_result = MagicMock()
    select_result.scalars.return_value.first.return_value = pause

    update_result = MagicMock()

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=[select_result, update_result])

    result = await MessageScheduleRepository.is_job_paused(session, JobName.FRIDAY)

    assert result is False
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()
