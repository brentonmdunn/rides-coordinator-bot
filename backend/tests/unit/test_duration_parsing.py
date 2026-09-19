"""Unit tests for parse_expiry (temporary driver duration/date parsing)."""

from datetime import UTC, datetime, timedelta

import pytest

from ridebot.utils.constants import TEMP_DRIVER_DEFAULT_DURATION, TEMP_DRIVER_MAX_DURATION
from ridebot.utils.duration_parsing import parse_expiry
from shared.utils.constants import LA_TZ

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestDefault:
    def test_none_uses_default_duration(self):
        result = parse_expiry(None, NOW)
        assert result == NOW + TEMP_DRIVER_DEFAULT_DURATION

    def test_blank_uses_default_duration(self):
        result = parse_expiry("   ", NOW)
        assert result == NOW + TEMP_DRIVER_DEFAULT_DURATION

    def test_empty_string_uses_default_duration(self):
        result = parse_expiry("", NOW)
        assert result == NOW + TEMP_DRIVER_DEFAULT_DURATION


class TestRelative:
    @pytest.mark.parametrize(
        "text,hours",
        [
            ("3h", 3),
            ("3hr", 3),
            ("3hrs", 3),
            ("3hour", 3),
            ("3hours", 3),
            ("3 h", 3),
            ("3H", 3),
        ],
    )
    def test_hours(self, text, hours):
        result = parse_expiry(text, NOW)
        assert result == NOW + timedelta(hours=hours)

    @pytest.mark.parametrize(
        "text",
        ["3d", "3day", "3days", "3 d", "3D"],
    )
    def test_days(self, text):
        result = parse_expiry(text, NOW)
        assert result == NOW + timedelta(days=3)

    @pytest.mark.parametrize(
        "text",
        ["2w", "2wk", "2wks", "2week", "2weeks", "2 w", "2W"],
    )
    def test_weeks(self, text):
        result = parse_expiry(text, NOW)
        assert result == NOW + timedelta(weeks=2)

    def test_zero_of_any_unit_is_in_the_past(self):
        with pytest.raises(ValueError, match="in the past"):
            parse_expiry("0d", NOW)

    def test_case_insensitive_and_whitespace_optional(self):
        assert parse_expiry("12H", NOW) == parse_expiry("12 h", NOW)


class TestDates:
    def test_iso_date(self):
        result = parse_expiry("2026-01-15", NOW)
        expected_la = LA_TZ.localize(datetime(2026, 1, 15, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_m_d_yy(self):
        result = parse_expiry("1/15/26", NOW)
        expected_la = LA_TZ.localize(datetime(2026, 1, 15, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_m_d_yyyy(self):
        result = parse_expiry("1/15/2026", NOW)
        expected_la = LA_TZ.localize(datetime(2026, 1, 15, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_m_d_this_year_when_still_upcoming(self):
        # NOW is 2026-01-01, so 3/5 (with no year) should resolve to this year.
        result = parse_expiry("3/5", NOW)
        expected_la = LA_TZ.localize(datetime(2026, 3, 5, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_m_d_rolls_to_next_year_when_passed(self):
        # "now" is late Dec 2025, so 1/2 (already passed this year) rolls to next Jan.
        now = datetime(2025, 12, 30, 12, 0, 0, tzinfo=UTC)
        result = parse_expiry("1/2", now)
        expected_la = LA_TZ.localize(datetime(2026, 1, 2, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_m_d_uses_this_year_when_today(self):
        # "Today" in LA counts as still upcoming.
        now_la = LA_TZ.localize(datetime(2026, 6, 15, 1, 0, 0))
        now = now_la.astimezone(UTC)
        result = parse_expiry("6/15", now)
        expected_la = LA_TZ.localize(datetime(2026, 6, 15, 23, 59, 59))
        assert result == expected_la.astimezone(UTC)

    def test_date_resolves_to_2359_59_la(self):
        result = parse_expiry("2026-01-20", NOW)
        la_result = result.astimezone(LA_TZ)
        assert (la_result.hour, la_result.minute, la_result.second) == (23, 59, 59)

    def test_dst_boundary_handled_correctly(self):
        # 2026-03-08 is the spring-forward DST transition in the US.
        result = parse_expiry("2026-03-08", NOW)
        la_result = result.astimezone(LA_TZ)
        assert (la_result.hour, la_result.minute, la_result.second) == (23, 59, 59)
        assert la_result.utcoffset().total_seconds() == -7 * 3600  # PDT after the switch


class TestLimits:
    def test_past_date_rejected(self):
        with pytest.raises(ValueError, match="in the past"):
            parse_expiry("2020-01-01", NOW)

    def test_exactly_now_is_in_the_past(self):
        with pytest.raises(ValueError, match="in the past"):
            parse_expiry("0h", NOW)

    def test_max_duration_accepted(self):
        result = parse_expiry("90d", NOW)
        assert result == NOW + TEMP_DRIVER_MAX_DURATION

    def test_beyond_max_duration_rejected(self):
        with pytest.raises(ValueError, match="90 days"):
            parse_expiry("91d", NOW)


class TestUnparseable:
    @pytest.mark.parametrize("text", ["xyz", "3zebras", "not a date", "13/45", "10-5-2026"])
    def test_garbage_input_rejected(self, text):
        with pytest.raises(ValueError, match="Couldn't understand duration"):
            parse_expiry(text, NOW)
