"""utils/time_helpers.py"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytz

from bot.core.enums import DaysOfWeek, DaysOfWeekNumber
from bot.utils.constants import (
    ACTIVE_HOURS_END,
    ACTIVE_HOURS_START,
    DAYS_IN_WEEK,
)

LA_TZ = pytz.timezone("America/Los_Angeles")

days_of_week_to_number = {
    DaysOfWeek.MONDAY: DaysOfWeekNumber.MONDAY,
    DaysOfWeek.TUESDAY: DaysOfWeekNumber.TUESDAY,
    DaysOfWeek.WEDNESDAY: DaysOfWeekNumber.WEDNESDAY,
    DaysOfWeek.THURSDAY: DaysOfWeekNumber.THURSDAY,
    DaysOfWeek.FRIDAY: DaysOfWeekNumber.FRIDAY,
    DaysOfWeek.SATURDAY: DaysOfWeekNumber.SATURDAY,
    DaysOfWeek.SUNDAY: DaysOfWeekNumber.SUNDAY,
}

# ---------------------------------------------------------------------------
# Unified time-window configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeWindow:
    """
    A time window: start_day @ start_hour:start_minute → end_day @ end_hour:end_minute.

    *start_minute* and *end_minute* default to 0 for backwards compatibility.
    The window may start and end on the same day.
    """

    start_day: DaysOfWeek
    start_hour: int
    end_day: DaysOfWeek
    end_hour: int
    start_minute: int = 0
    end_minute: int = 0


RIDE_DAY_WINDOWS: dict[DaysOfWeek, TimeWindow] = {
    DaysOfWeek.WEDNESDAY: TimeWindow(
        start_day=DaysOfWeek.TUESDAY,
        start_hour=19,
        end_day=DaysOfWeek.WEDNESDAY,
        end_hour=19,
    ),
    DaysOfWeek.FRIDAY: TimeWindow(
        start_day=DaysOfWeek.THURSDAY,
        start_hour=19,
        end_day=DaysOfWeek.FRIDAY,
        end_hour=19,
    ),
    DaysOfWeek.SUNDAY: TimeWindow(
        start_day=DaysOfWeek.SATURDAY,
        start_hour=10,
        end_day=DaysOfWeek.SUNDAY,
        end_hour=10,
    ),
}

LATE_REACTION_WINDOWS: dict[DaysOfWeek, TimeWindow] = {
    DaysOfWeek.WEDNESDAY: TimeWindow(
        start_day=DaysOfWeek.TUESDAY,
        start_hour=19,
        end_day=DaysOfWeek.WEDNESDAY,
        end_hour=19,
    ),
    DaysOfWeek.FRIDAY: TimeWindow(
        start_day=DaysOfWeek.THURSDAY,
        start_hour=19,
        end_day=DaysOfWeek.FRIDAY,
        end_hour=19,
    ),
    DaysOfWeek.SUNDAY: TimeWindow(
        start_day=DaysOfWeek.SATURDAY,
        start_hour=10,
        end_day=DaysOfWeek.SUNDAY,
        end_hour=10,
    ),
}

# ---------------------------------------------------------------------------
# Ride-coverage widget and message-lookup windows
# ---------------------------------------------------------------------------

# Controls when the coverage widget is visible in the UI.
COVERAGE_WIDGET_WINDOWS: dict[str, TimeWindow] = {
    "friday": TimeWindow(
        start_day=DaysOfWeek.FRIDAY,
        start_hour=11,
        start_minute=0,
        end_day=DaysOfWeek.FRIDAY,
        end_hour=23,
        end_minute=59,
    ),
    "sunday": TimeWindow(
        start_day=DaysOfWeek.SATURDAY,
        start_hour=15,
        start_minute=0,
        end_day=DaysOfWeek.SUNDAY,
        end_hour=13,
        end_minute=0,
    ),
}

# Controls which Discord grouping ("drive:") messages count as coverage entries.
COVERAGE_MESSAGE_LOOKUP_WINDOWS: dict[str, TimeWindow] = {
    "friday": TimeWindow(
        start_day=DaysOfWeek.FRIDAY,
        start_hour=11,
        start_minute=0,
        end_day=DaysOfWeek.FRIDAY,
        end_hour=19,
        end_minute=30,
    ),
    "sunday": TimeWindow(
        start_day=DaysOfWeek.SATURDAY,
        start_hour=15,
        start_minute=0,
        end_day=DaysOfWeek.SUNDAY,
        end_hour=10,
        end_minute=30,
    ),
}


def is_in_coverage_widget_window(ride_type: str) -> bool:
    """Return True if the coverage widget for *ride_type* should be visible right now."""
    window = COVERAGE_WIDGET_WINDOWS.get(ride_type.lower())
    return _check_time_window(window, datetime.now(tz=LA_TZ)) if window else False


def is_in_any_coverage_message_lookup_window() -> bool:
    """Return True if the current time falls in any coverage message lookup window."""
    now = datetime.now(tz=LA_TZ)
    return any(_check_time_window(w, now) for w in COVERAGE_MESSAGE_LOOKUP_WINDOWS.values())


def is_message_in_any_coverage_lookup_window(message_dt: datetime) -> bool:
    """
    Return True if *message_dt* falls within any coverage message lookup window.

    Args:
        message_dt: A timezone-aware datetime (e.g. ``message.created_at`` from Discord).
    """
    la_dt = message_dt.astimezone(LA_TZ)
    return any(_check_time_window(w, la_dt) for w in COVERAGE_MESSAGE_LOOKUP_WINDOWS.values())


def get_coverage_message_lookup_start(ride_type: str) -> datetime | None:
    """
    Return the start of the message lookup window for the most recent cycle.

    For ``"friday"``: most recent Friday at 12:00 LA.
    For ``"sunday"``: most recent Saturday at 15:00 LA.

    Returns ``None`` if *ride_type* is unrecognized.
    """
    window = COVERAGE_MESSAGE_LOOKUP_WINDOWS.get(ride_type.lower())
    if window is None:
        return None

    now = datetime.now(tz=LA_TZ)
    target_weekday = int(days_of_week_to_number[window.start_day])
    days_since = (now.weekday() - target_weekday) % DAYS_IN_WEEK
    start_date = (now - timedelta(days=days_since)).date()

    return LA_TZ.localize(
        datetime(
            start_date.year,
            start_date.month,
            start_date.day,
            window.start_hour,
            window.start_minute,
            0,
        )
    )


def _resolve_day(day: str | DaysOfWeek) -> DaysOfWeek | None:
    """Resolve a day string or enum to a ``DaysOfWeek`` member."""
    if isinstance(day, DaysOfWeek):
        return day
    try:
        return DaysOfWeek(day.capitalize())
    except ValueError:
        return None


def _check_time_window(window: TimeWindow, now: datetime) -> bool:
    """Return True if *now* (LA-aware) falls inside *window*."""
    weekday_enum = list(DaysOfWeek)[now.weekday()]
    now_minutes = now.hour * 60 + now.minute
    start_minutes = window.start_hour * 60 + window.start_minute
    end_minutes = window.end_hour * 60 + window.end_minute

    if window.start_day == window.end_day:
        return weekday_enum == window.start_day and start_minutes <= now_minutes <= end_minutes
    return (weekday_enum == window.start_day and now_minutes >= start_minutes) or (
        weekday_enum == window.end_day and now_minutes < end_minutes
    )


def _is_in_window(day: str | DaysOfWeek, windows: dict[DaysOfWeek, TimeWindow]) -> bool:
    """Check if the current LA time falls inside the window for *day*."""
    day_enum = _resolve_day(day)
    if day_enum is None:
        return False

    window = windows.get(day_enum)
    if window is None:
        return False

    return _check_time_window(window, datetime.now(tz=LA_TZ))


def is_in_ride_day_window(day: str | DaysOfWeek) -> bool:
    """
    Checks if the current time in LA is within the ride-day window for the given day.

    Windows are defined in ``RIDE_DAY_WINDOWS``.

    Args:
        day: The day to check (Wednesday, Friday, or Sunday).
             Accepts a string or a ``DaysOfWeek`` enum member.

    Returns:
        bool: True if the current time is within the window, False otherwise.
    """
    return _is_in_window(day, RIDE_DAY_WINDOWS)


def is_in_late_reaction_window(day: str | DaysOfWeek) -> bool:
    """
    Checks if the current time in LA is within the late-reaction window for the given day.

    Windows are defined in ``LATE_REACTION_WINDOWS``.

    Args:
        day: The day to check (Wednesday, Friday, or Sunday).
             Accepts a string or a ``DaysOfWeek`` enum member.

    Returns:
        bool: True if the current time is within the window, False otherwise.
    """
    return _is_in_window(day, LATE_REACTION_WINDOWS)


def get_next_date_str(day: DaysOfWeekNumber) -> str:
    """
    Gets the next `day` and returns it in mm/dd form.

    Args:
        day (DaysOfWeekNumber): The day of the week to find the next date for.

    Returns:
        str: The formatted date string (mm/dd).
    """
    today = datetime.now(tz=LA_TZ)
    days_ahead = (day - today.weekday() + DAYS_IN_WEEK) % DAYS_IN_WEEK
    if days_ahead == 0:
        days_ahead = DAYS_IN_WEEK  # Skip to next day if `day` is current day

    next_day = today + timedelta(days=days_ahead)
    formatted_date = next_day.strftime("%-m/%-d")
    return formatted_date


def get_next_date_obj(day: DaysOfWeek) -> date:
    """
    Gets the next `day` as a date object.

    Args:
        day (DaysOfWeek): The day of the week to find the next date for.

    Returns:
        date: The date object for the next occurrence of the given day.
    """
    day_num = days_of_week_to_number[day]
    today = datetime.now(tz=LA_TZ)
    days_ahead = (day_num - today.weekday() + DAYS_IN_WEEK) % DAYS_IN_WEEK
    if days_ahead == 0:
        days_ahead = DAYS_IN_WEEK  # Skip to next day if `day` is current day

    # The key change is here: we convert the final datetime object to a date object
    return (today + timedelta(days=days_ahead)).date()


def get_last_sunday() -> datetime:
    """
    Calculates the date of the last Sunday.

    Returns:
        datetime: The datetime object for the last Sunday.
    """
    now = datetime.now(tz=LA_TZ)
    days_to_subtract = (now.weekday() + 1) % DAYS_IN_WEEK
    if days_to_subtract == 0:
        days_to_subtract = DAYS_IN_WEEK
    return now - timedelta(days=days_to_subtract)


def is_active_hours() -> bool:
    """
    Check if current time is within active hours (7 AM - 1 AM Pacific).

    Active hours: 7:00 AM through 12:59 AM (i.e. hour >= 7 or hour < 1).
    Off-hours: 1:00 AM through 6:59 AM.

    Returns:
        True if within active hours, False otherwise.
    """
    hour = datetime.now(tz=LA_TZ).hour
    return hour >= ACTIVE_HOURS_START or hour < ACTIVE_HOURS_END


def get_current_cycle_start() -> datetime:
    """
    Return the start of the current ask-rides cycle: the most recent Monday at 00:00.

    The ride cycle is defined as the calendar week (Monday 00:00 -> Sunday
    23:59). On Monday itself this returns today at 00:00.

    Returns:
        datetime of the most recent Monday at 00:00:00.
    """
    now = datetime.now(tz=LA_TZ)
    week_start = now - timedelta(days=now.weekday())
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


def get_send_wednesday(event_date: date) -> date:
    """
    Calculate the Wednesday send-day before an event date.

    Args:
        event_date: The event date (a Friday or Sunday).

    Returns:
        The Wednesday immediately before the event date.
    """
    return get_send_day_before(event_date, DaysOfWeekNumber.WEDNESDAY)


def get_send_day_before(event_date: date, day_of_week: int) -> date:
    """
    Calculate the configured send day immediately before an event date.

    Generalizes ``get_send_wednesday`` to an arbitrary send day, so pause
    auto-resume logic can be schedule-aware instead of hardcoding Wednesday.

    Args:
        event_date: The event date the send announces.
        day_of_week: 0=Monday .. 6=Sunday (matches DaysOfWeekNumber) — the
            configured send day for the governing schedule slot.

    Returns:
        The most recent occurrence of *day_of_week* on or before *event_date*.
    """
    days_to_subtract = (event_date.weekday() - day_of_week) % DAYS_IN_WEEK
    return event_date - timedelta(days=days_to_subtract)


def is_during_late_reaction_window(message_content: str) -> bool:
    """
    Check if the current time is within a late-reaction window for any ride
    announcement day (Wednesday, Friday, Sunday) mentioned in the message.

    Args:
        message_content: The text of the ride announcement message.

    Returns:
        True if we're inside the target window for a day named in the message.
    """
    content = message_content.lower()
    return (
        ("friday" in content and is_in_late_reaction_window(DaysOfWeek.FRIDAY))
        or ("sunday" in content and is_in_late_reaction_window(DaysOfWeek.SUNDAY))
        or ("wednesday" in content and is_in_late_reaction_window(DaysOfWeek.WEDNESDAY))
    )
