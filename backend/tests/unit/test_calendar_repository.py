"""Unit tests for CalendarRepository (data access layer)."""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.repositories.calendar_repository import CalendarRepository


class _FakeEvent(dict):
    """Minimal iCal event dict-like object."""

    def get(self, key, default=None):
        return super().get(key, default)


def _make_event(summary: str) -> _FakeEvent:
    return _FakeEvent({"SUMMARY": summary})


# ---------------------------------------------------------------------------
# get_events_on_date
# ---------------------------------------------------------------------------


@patch("shared.repositories.calendar_repository.ICAL_URL", None)
@pytest.mark.asyncio
async def test_get_events_on_date_no_url_returns_empty():
    """Should return [] and log an error when ICAL_URL is not set."""
    result = await CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))
    assert result == []


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("shared.repositories.calendar_repository.recurring_ical_events")
@patch("shared.repositories.calendar_repository.Calendar")
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

    with patch(
        "shared.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client
    ):
        result = await CalendarRepository.get_events_on_date(target)

    mock_calendar_cls.from_ical.assert_called_once_with("VCALENDAR_DATA")
    mock_rie.of.return_value.at.assert_called_once_with(target)
    assert result == [fake_event]


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@pytest.mark.asyncio
async def test_get_events_on_date_request_exception_returns_empty():
    """Should return [] when a network error occurs."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))

    with patch(
        "shared.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client
    ):
        result = await CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))

    assert result == []


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("shared.repositories.calendar_repository.Calendar")
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

    with patch(
        "shared.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client
    ):
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


# ---------------------------------------------------------------------------
# get_event_summaries_by_date
# ---------------------------------------------------------------------------


@patch("shared.repositories.calendar_repository.ICAL_URL", None)
@pytest.mark.asyncio
async def test_get_event_summaries_by_date_no_url_returns_empty_dict():
    """Should return {} when ICAL_URL is not set."""
    result = await CalendarRepository.get_event_summaries_by_date(
        datetime.date(2026, 5, 11), datetime.date(2026, 5, 17)
    )
    assert result == {}


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@pytest.mark.asyncio
async def test_get_event_summaries_by_date_rejects_inverted_range():
    """Should return {} when end_date precedes start_date, without fetching."""
    with patch("shared.repositories.calendar_repository.httpx.AsyncClient") as mock_client_cls:
        result = await CalendarRepository.get_event_summaries_by_date(
            datetime.date(2026, 5, 17), datetime.date(2026, 5, 11)
        )
    assert result == {}
    mock_client_cls.assert_not_called()


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("shared.repositories.calendar_repository.recurring_ical_events")
@patch("shared.repositories.calendar_repository.Calendar")
@pytest.mark.asyncio
async def test_get_event_summaries_by_date_groups_by_day(mock_calendar_cls, mock_rie):
    """Should return every date in the range, grouping summaries per day."""
    mock_response = MagicMock()
    mock_response.text = "BEGIN:VCALENDAR"
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    events_by_day = {
        datetime.date(2026, 5, 11): [_make_event("Prayer Night")],
        datetime.date(2026, 5, 14): [_make_event("Bible Study"), _make_event("Choir")],
    }
    query = MagicMock()
    query.at.side_effect = lambda day: events_by_day.get(day, [])
    mock_rie.of.return_value = query

    with patch(
        "shared.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client
    ):
        result = await CalendarRepository.get_event_summaries_by_date(
            datetime.date(2026, 5, 11), datetime.date(2026, 5, 17)
        )

    assert len(result) == 7
    assert result[datetime.date(2026, 5, 11)] == ["Prayer Night"]
    assert result[datetime.date(2026, 5, 14)] == ["Bible Study", "Choir"]
    assert result[datetime.date(2026, 5, 12)] == []
    assert result[datetime.date(2026, 5, 17)] == []
    # The feed is downloaded once for the whole range, not once per day.
    assert mock_client.get.await_count == 1


@patch("shared.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("shared.repositories.calendar_repository.recurring_ical_events")
@patch("shared.repositories.calendar_repository.Calendar")
@pytest.mark.asyncio
async def test_get_event_summaries_by_date_survives_bad_day(mock_calendar_cls, mock_rie):
    """A day that fails to expand should yield [] rather than aborting the range."""
    mock_response = MagicMock()
    mock_response.text = "BEGIN:VCALENDAR"
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    def _at(day):
        if day == datetime.date(2026, 5, 12):
            raise ValueError("bad recurrence")
        return [_make_event("Prayer Night")]

    query = MagicMock()
    query.at.side_effect = _at
    mock_rie.of.return_value = query

    with patch(
        "shared.repositories.calendar_repository.httpx.AsyncClient", return_value=mock_client
    ):
        result = await CalendarRepository.get_event_summaries_by_date(
            datetime.date(2026, 5, 11), datetime.date(2026, 5, 13)
        )

    assert result[datetime.date(2026, 5, 12)] == []
    assert result[datetime.date(2026, 5, 11)] == ["Prayer Night"]
    assert result[datetime.date(2026, 5, 13)] == ["Prayer Night"]
