"""Unit tests for CalendarRepository (data access layer)."""

import datetime
from unittest.mock import MagicMock, patch

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
def test_get_events_on_date_no_url_returns_empty():
    """Should return [] and log an error when ICAL_URL is not set."""
    result = CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))
    assert result == []


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("bot.repositories.calendar_repository.recurring_ical_events")
@patch("bot.repositories.calendar_repository.Calendar")
@patch("bot.repositories.calendar_repository.requests")
def test_get_events_on_date_returns_events(mock_requests, mock_calendar_cls, mock_rie):
    """Should return events list when download and parsing succeed."""
    target = datetime.date(2026, 5, 10)

    mock_response = MagicMock()
    mock_response.text = "VCALENDAR_DATA"
    mock_requests.get.return_value = mock_response

    mock_cal = MagicMock()
    mock_calendar_cls.from_ical.return_value = mock_cal

    fake_event = _make_event("Sunday Service")
    mock_rie.of.return_value.at.return_value = [fake_event]

    result = CalendarRepository.get_events_on_date(target)

    mock_requests.get.assert_called_once_with("http://example.com/cal.ics")
    mock_response.raise_for_status.assert_called_once()
    mock_calendar_cls.from_ical.assert_called_once_with("VCALENDAR_DATA")
    mock_rie.of.return_value.at.assert_called_once_with(target)
    assert result == [fake_event]


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("bot.repositories.calendar_repository.requests")
def test_get_events_on_date_request_exception_returns_empty(mock_requests):
    """Should return [] when a network error occurs."""
    import requests as req_lib

    mock_requests.get.side_effect = req_lib.exceptions.RequestException("timeout")
    mock_requests.exceptions.RequestException = req_lib.exceptions.RequestException

    result = CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))
    assert result == []


@patch("bot.repositories.calendar_repository.ICAL_URL", "http://example.com/cal.ics")
@patch("bot.repositories.calendar_repository.Calendar")
@patch("bot.repositories.calendar_repository.requests")
def test_get_events_on_date_value_error_returns_empty(mock_requests, mock_calendar_cls):
    """Should return [] when iCal parsing raises ValueError."""
    import requests as req_lib

    mock_response = MagicMock()
    mock_response.text = "BAD_DATA"
    mock_requests.get.return_value = mock_response
    mock_requests.exceptions.RequestException = req_lib.exceptions.RequestException

    mock_calendar_cls.from_ical.side_effect = ValueError("bad ical")

    result = CalendarRepository.get_events_on_date(datetime.date(2026, 5, 10))
    assert result == []


# ---------------------------------------------------------------------------
# get_event_summaries
# ---------------------------------------------------------------------------


@patch.object(CalendarRepository, "get_events_on_date", return_value=[])
def test_get_event_summaries_no_events(mock_get):
    """Should return [] when there are no events."""
    result = CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == []
    mock_get.assert_called_once_with(datetime.date(2026, 5, 10))


@patch.object(
    CalendarRepository,
    "get_events_on_date",
    return_value=[_make_event("Sunday Service"), _make_event("Bible Study")],
)
def test_get_event_summaries_returns_summaries(mock_get):
    """Should return a list of summary strings for all events."""
    result = CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == ["Sunday Service", "Bible Study"]


@patch.object(
    CalendarRepository,
    "get_events_on_date",
    return_value=[_make_event("Single Event")],
)
def test_get_event_summaries_single_event(mock_get):
    """Should handle a single event correctly."""
    result = CalendarRepository.get_event_summaries(datetime.date(2026, 5, 10))
    assert result == ["Single Event"]
