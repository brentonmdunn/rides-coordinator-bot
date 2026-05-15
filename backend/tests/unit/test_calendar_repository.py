"""Unit tests for CalendarRepository (data access layer)."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.repositories.calendar_repository import CalendarRepository


class _FakeEvent(dict):
    """Minimal iCal event dict-like object."""

    def get(self, key, default=None):
        return super().get(key, default)


def _make_event(summary: str) -> _FakeEvent:
    return _FakeEvent({"SUMMARY": summary})


# ---------------------------------------------------------------------------
# get_events_on_date
# ---------------------------------------------------------------------------


@patch("bot.repositories.calendar_repository.ICAL_URL", None)
@pytest.mark.asyncio
async def test_get_events_on_date_no_url_returns_empty():
    """Should return [] and log an error when ICAL_URL is not set."""
    result = await CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))
    assert result == []


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("bot.repositories.calendar_repository.recurring_ical_events")
@patch("bot.repositories.calendar_repository.Calendar")
@pytest.mark.asyncio
async def test_get_events_on_date_returns_events(mock_calendar_cls, mock_rie):
    """Should return events list when download and parsing succeed."""
    target = datetime.date(2026, 5, 10)

    mock_response = MagicMock()
    mock_response.text = "VCALENDAR_DATA"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    fake_event = _make_event("Sunday Service")
    mock_cal = MagicMock()
    mock_calendar_cls.from_ical.return_value = mock_cal
    mock_rie.of.return_value.at.return_value = [fake_event]

    with patch("bot.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client):
        result = await CalendarRepository.get_events_on_date(target)

    mock_calendar_cls.from_ical.assert_called_once_with("VCALENDAR_DATA")
    mock_rie.of.return_value.at.assert_called_once_with(target)
    assert result == [fake_event]


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@pytest.mark.asyncio
async def test_get_events_on_date_request_exception_returns_empty():
    """Should return [] when a network error occurs."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))

    with patch("bot.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client):
        result = await CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))

    assert result == []


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("bot.repositories.calendar_repository.Calendar")
@pytest.mark.asyncio
async def test_get_events_on_date_value_error_returns_empty(mock_calendar_cls):
    """Should return [] when iCal parsing raises ValueError."""
    mock_response = MagicMock()
    mock_response.text = "BAD_DATA"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_calendar_cls.from_ical.side_effect = ValueError("bad ical")

    with patch("bot.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client):
        result = await CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))

    assert result == []


# ---------------------------------------------------------------------------
# get_event_summaries
# ---------------------------------------------------------------------------


@patch.object(CalendarRepository, "get_events_on_date", new_callable=AsyncMock, return_value=[])
@pytest.mark.asyncio
async def test_get_event_summaries_no_events(mock_get):
    """Should return [] when there are no events."""
    result = await CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == []
    mock_get.assert_awaited_once_with(datetime.date(2026, 5, 10))


@patch.object(
    CalendarRepository,
    "get_events_on_date",
    new_callable=AsyncMock,
    return_value=[_make_event("Sunday Service"), _make_event("Bible Study")],
)
@pytest.mark.asyncio
async def test_get_event_summaries_returns_summaries(mock_get):
    """Should return a list of summary strings for all events."""
    result = await CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == ["Sunday Service", "Bible Study"]


@patch.object(
    CalendarRepository,
    "get_events_on_date",
    new_callable=AsyncMock,
    return_value=[_make_event("Single Event")],
)
@pytest.mark.asyncio
async def test_get_event_summaries_single_event(mock_get):
    """Should handle a single event correctly."""
    result = await CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == ["Single Event"]
