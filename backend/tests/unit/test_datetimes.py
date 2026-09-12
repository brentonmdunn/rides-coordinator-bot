"""Unit tests for shared/utils/datetimes.py."""

from datetime import UTC, datetime, timedelta, timezone

from shared.utils.datetimes import to_iso_utc


def test_none_passes_through():
    assert to_iso_utc(None) is None


def test_naive_is_treated_as_utc():
    """SQLite returns naive datetimes; they were written as UTC."""
    assert to_iso_utc(datetime(2024, 1, 1, 22, 30)) == "2024-01-01T22:30:00+00:00"


def test_aware_utc_keeps_offset():
    assert to_iso_utc(datetime(2024, 1, 1, 22, 30, tzinfo=UTC)) == "2024-01-01T22:30:00+00:00"


def test_other_offset_is_converted_to_utc():
    value = datetime(2024, 1, 1, 12, 30, tzinfo=timezone(timedelta(hours=-10)))
    assert to_iso_utc(value) == "2024-01-01T22:30:00+00:00"


def test_result_always_carries_an_offset():
    """A missing offset is the bug: browsers parse such strings as local time."""
    for value in (datetime(2024, 6, 1, 5, 0), datetime(2024, 6, 1, 5, 0, tzinfo=UTC)):
        assert to_iso_utc(value).endswith("+00:00")
