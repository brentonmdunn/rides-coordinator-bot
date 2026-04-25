"""Extensive unit tests for bot.utils.time_helpers."""

from datetime import date, datetime
from unittest.mock import patch

import pytz

from bot.core.enums import DaysOfWeek, DaysOfWeekNumber
from bot.utils.time_helpers import (
    LA_TZ,
    get_current_cycle_start,
    get_last_sunday,
    get_next_date_obj,
    get_next_date_str,
    get_next_wednesday_noon,
    get_send_wednesday,
    is_active_hours,
    is_during_late_reaction_window,
    is_in_ride_day_window,
    is_ride_cycle_active,
)


def _la(year, month, day, hour=0, minute=0):
    """Helper to build a timezone-aware LA datetime."""
    return LA_TZ.localize(datetime(year, month, day, hour, minute))


# ---------------------------------------------------------------------------
# is_in_ride_day_window
# ---------------------------------------------------------------------------
class TestIsInRideDayWindow:
    """Tests for the ride-day window checker."""

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_window_tuesday_before_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 21, 18, 0)  # Tuesday 6 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Wednesday") is False

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_window_tuesday_at_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 21, 19, 0)  # Tuesday 7 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Wednesday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_window_wednesday_before_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 12, 0)  # Wednesday noon
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Wednesday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_window_wednesday_at_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 19, 0)  # Wednesday 7 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Wednesday") is False

    @patch("bot.utils.time_helpers.datetime")
    def test_friday_window_thursday_at_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 23, 19, 0)  # Thursday 7 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Friday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_friday_window_friday_before_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 24, 14, 0)  # Friday 2 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Friday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_friday_window_friday_at_7pm(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 24, 19, 0)  # Friday 7 PM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Friday") is False

    @patch("bot.utils.time_helpers.datetime")
    def test_sunday_window_saturday_at_10am(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 25, 10, 0)  # Saturday 10 AM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Sunday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_sunday_window_saturday_before_10am(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 25, 9, 0)  # Saturday 9 AM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Sunday") is False

    @patch("bot.utils.time_helpers.datetime")
    def test_sunday_window_sunday_before_10am(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 26, 9, 0)  # Sunday 9 AM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Sunday") is True

    @patch("bot.utils.time_helpers.datetime")
    def test_sunday_window_sunday_at_10am(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 26, 10, 0)  # Sunday 10 AM
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert is_in_ride_day_window("Sunday") is False

    def test_invalid_day_returns_false(self):
        assert is_in_ride_day_window("Monday") is False

    def test_garbage_day_returns_false(self):
        assert is_in_ride_day_window("notaday") is False

    def test_lowercase_day(self):
        # Should handle capitalisation via .capitalize()
        result = is_in_ride_day_window("wednesday")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# get_next_date_str
# ---------------------------------------------------------------------------
class TestGetNextDateStr:
    """Tests for get_next_date_str."""

    @patch("bot.utils.time_helpers.datetime")
    def test_returns_next_wednesday_from_monday(self, mock_dt):
        # Monday April 20, 2026
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_str(DaysOfWeekNumber.WEDNESDAY)
        assert result == "4/22"

    @patch("bot.utils.time_helpers.datetime")
    def test_skips_to_next_week_on_same_day(self, mock_dt):
        # Wednesday April 22, 2026
        mock_dt.now.return_value = _la(2026, 4, 22, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_str(DaysOfWeekNumber.WEDNESDAY)
        assert result == "4/29"

    @patch("bot.utils.time_helpers.datetime")
    def test_next_friday_from_thursday(self, mock_dt):
        # Thursday April 23, 2026
        mock_dt.now.return_value = _la(2026, 4, 23, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_str(DaysOfWeekNumber.FRIDAY)
        assert result == "4/24"

    @patch("bot.utils.time_helpers.datetime")
    def test_next_sunday_from_saturday(self, mock_dt):
        # Saturday April 25, 2026
        mock_dt.now.return_value = _la(2026, 4, 25, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_str(DaysOfWeekNumber.SUNDAY)
        assert result == "4/26"


# ---------------------------------------------------------------------------
# get_next_date_obj
# ---------------------------------------------------------------------------
class TestGetNextDateObj:
    """Tests for get_next_date_obj."""

    @patch("bot.utils.time_helpers.datetime")
    def test_returns_date_object(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_obj(DaysOfWeek.FRIDAY)
        assert isinstance(result, date)
        assert result == date(2026, 4, 24)

    @patch("bot.utils.time_helpers.datetime")
    def test_skips_same_day(self, mock_dt):
        # Sunday April 26, 2026
        mock_dt.now.return_value = _la(2026, 4, 26, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_date_obj(DaysOfWeek.SUNDAY)
        assert result == date(2026, 5, 3)

    @patch("bot.utils.time_helpers.datetime")
    def test_every_day_of_week(self, mock_dt):
        # Wednesday April 22, 2026
        mock_dt.now.return_value = _la(2026, 4, 22, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        for day_enum in DaysOfWeek:
            result = get_next_date_obj(day_enum)
            assert isinstance(result, date)
            # Should never be today
            assert result > date(2026, 4, 22)


# ---------------------------------------------------------------------------
# get_last_sunday
# ---------------------------------------------------------------------------
class TestGetLastSunday:
    """Tests for get_last_sunday."""

    @patch("bot.utils.time_helpers.datetime")
    def test_on_monday(self, mock_dt):
        # Monday April 20, 2026
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_last_sunday()
        assert result.weekday() == 6  # Sunday
        assert result.date() == date(2026, 4, 19)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_sunday_returns_previous_sunday(self, mock_dt):
        # Sunday April 26, 2026
        mock_dt.now.return_value = _la(2026, 4, 26, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_last_sunday()
        assert result.date() == date(2026, 4, 19)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_saturday(self, mock_dt):
        # Saturday April 25, 2026
        mock_dt.now.return_value = _la(2026, 4, 25, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_last_sunday()
        assert result.date() == date(2026, 4, 19)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_wednesday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_last_sunday()
        assert result.date() == date(2026, 4, 19)


# ---------------------------------------------------------------------------
# is_active_hours
# ---------------------------------------------------------------------------
class TestIsActiveHours:
    """Tests for is_active_hours."""

    @patch("bot.utils.time_helpers.datetime")
    def test_midnight_is_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 0, 30)  # 12:30 AM
        assert is_active_hours() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_1am_is_not_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 1, 0)
        assert is_active_hours() is False

    @patch("bot.utils.time_helpers.datetime")
    def test_3am_is_not_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 3, 0)
        assert is_active_hours() is False

    @patch("bot.utils.time_helpers.datetime")
    def test_6am_is_not_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 6, 59)
        assert is_active_hours() is False

    @patch("bot.utils.time_helpers.datetime")
    def test_7am_is_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 7, 0)
        assert is_active_hours() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_noon_is_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 12, 0)
        assert is_active_hours() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_11pm_is_active(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 23, 0)
        assert is_active_hours() is True


# ---------------------------------------------------------------------------
# is_ride_cycle_active
# ---------------------------------------------------------------------------
class TestIsRideCycleActive:
    """Tests for is_ride_cycle_active."""

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_before_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 11, 0)
        assert is_ride_cycle_active() is False

    @patch("bot.utils.time_helpers.datetime")
    def test_wednesday_at_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 12, 0)
        assert is_ride_cycle_active() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_thursday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 23, 10, 0)
        assert is_ride_cycle_active() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_sunday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 26, 23, 0)
        assert is_ride_cycle_active() is True

    @patch("bot.utils.time_helpers.datetime")
    def test_monday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        assert is_ride_cycle_active() is False

    @patch("bot.utils.time_helpers.datetime")
    def test_tuesday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 21, 10, 0)
        assert is_ride_cycle_active() is False


# ---------------------------------------------------------------------------
# get_current_cycle_start
# ---------------------------------------------------------------------------
class TestGetCurrentCycleStart:
    """Tests for get_current_cycle_start."""

    @patch("bot.utils.time_helpers.datetime")
    def test_on_thursday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 23, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_current_cycle_start()
        assert result.weekday() == DaysOfWeekNumber.WEDNESDAY
        assert result.hour == 12
        assert result.date() == date(2026, 4, 22)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_wednesday_after_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_current_cycle_start()
        assert result.date() == date(2026, 4, 22)
        assert result.hour == 12

    @patch("bot.utils.time_helpers.datetime")
    def test_on_monday_goes_back_to_previous_wednesday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_current_cycle_start()
        assert result.weekday() == DaysOfWeekNumber.WEDNESDAY
        assert result.date() == date(2026, 4, 8)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_sunday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 26, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_current_cycle_start()
        assert result.date() == date(2026, 4, 22)


# ---------------------------------------------------------------------------
# get_next_wednesday_noon
# ---------------------------------------------------------------------------
class TestGetNextWednesdayNoon:
    """Tests for get_next_wednesday_noon."""

    @patch("bot.utils.time_helpers.datetime")
    def test_on_monday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 20, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_wednesday_noon()
        assert result.weekday() == DaysOfWeekNumber.WEDNESDAY
        assert result.hour == 12
        assert result.date() == date(2026, 4, 22)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_wednesday_before_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 11, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_wednesday_noon()
        assert result.date() == date(2026, 4, 22)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_wednesday_at_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_wednesday_noon()
        assert result.date() == date(2026, 4, 29)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_wednesday_after_noon(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 22, 15, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_wednesday_noon()
        assert result.date() == date(2026, 4, 29)

    @patch("bot.utils.time_helpers.datetime")
    def test_on_friday(self, mock_dt):
        mock_dt.now.return_value = _la(2026, 4, 24, 10, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = get_next_wednesday_noon()
        assert result.date() == date(2026, 4, 29)


# ---------------------------------------------------------------------------
# get_send_wednesday
# ---------------------------------------------------------------------------
class TestGetSendWednesday:
    """Tests for get_send_wednesday."""

    def test_friday_event(self):
        # Friday April 24, 2026
        result = get_send_wednesday(date(2026, 4, 24))
        assert result == date(2026, 4, 22)

    def test_sunday_event(self):
        # Sunday April 26, 2026
        result = get_send_wednesday(date(2026, 4, 26))
        assert result == date(2026, 4, 22)

    def test_wednesday_event_returns_same_day(self):
        result = get_send_wednesday(date(2026, 4, 22))
        assert result == date(2026, 4, 22)

    def test_thursday_event(self):
        result = get_send_wednesday(date(2026, 4, 23))
        assert result == date(2026, 4, 22)

    def test_monday_event(self):
        # Monday April 20 -> previous Wednesday April 15
        result = get_send_wednesday(date(2026, 4, 20))
        assert result == date(2026, 4, 15)


# ---------------------------------------------------------------------------
# is_during_late_reaction_window
# ---------------------------------------------------------------------------
class TestIsDuringLateReactionWindow:
    """Tests for is_during_late_reaction_window."""

    @patch("bot.utils.time_helpers.is_in_ride_day_window")
    def test_friday_message_in_window(self, mock_window):
        mock_window.return_value = True
        assert is_during_late_reaction_window("React for Friday fellowship 4/24") is True

    @patch("bot.utils.time_helpers.is_in_ride_day_window")
    def test_sunday_message_in_window(self, mock_window):
        mock_window.return_value = True
        assert is_during_late_reaction_window("React for Sunday service 4/26") is True

    @patch("bot.utils.time_helpers.is_in_ride_day_window")
    def test_wednesday_message_in_window(self, mock_window):
        mock_window.return_value = True
        assert is_during_late_reaction_window("React for Wednesday Bible study") is True

    @patch("bot.utils.time_helpers.is_in_ride_day_window")
    def test_no_day_in_message(self, mock_window):
        mock_window.return_value = True
        assert is_during_late_reaction_window("React for rides!") is False

    @patch("bot.utils.time_helpers.is_in_ride_day_window")
    def test_day_in_message_but_not_in_window(self, mock_window):
        mock_window.return_value = False
        assert is_during_late_reaction_window("React for Friday fellowship") is False

    def test_case_insensitive(self):
        # Just checks it doesn't crash on case variations
        result = is_during_late_reaction_window("FRIDAY rides")
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# LA_TZ constant
# ---------------------------------------------------------------------------
class TestLATZ:
    """Tests for the LA_TZ constant."""

    def test_la_tz_is_pacific(self):
        assert str(LA_TZ) == "America/Los_Angeles"

    def test_la_tz_is_pytz_timezone(self):
        assert pytz.timezone("America/Los_Angeles") == LA_TZ
