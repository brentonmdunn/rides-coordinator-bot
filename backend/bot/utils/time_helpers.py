"""utils/time_helpers.py"""

from datetime import date, datetime, timedelta

import pytz

from bot.core.enums import DaysOfWeek, DaysOfWeekNumber

days_of_week_to_number = {
    DaysOfWeek.MONDAY: DaysOfWeekNumber.MONDAY,
    DaysOfWeek.TUESDAY: DaysOfWeekNumber.TUESDAY,
    DaysOfWeek.WEDNESDAY: DaysOfWeekNumber.WEDNESDAY,
    DaysOfWeek.THURSDAY: DaysOfWeekNumber.THURSDAY,
    DaysOfWeek.FRIDAY: DaysOfWeekNumber.FRIDAY,
    DaysOfWeek.SATURDAY: DaysOfWeekNumber.SATURDAY,
    DaysOfWeek.SUNDAY: DaysOfWeekNumber.SUNDAY,
}


def is_in_ride_day_window(day: str) -> bool:
    """
    Checks if the current time in LA is within the target window for the given day.

    The windows are:
    - Tuesday 7 PM to Wednesday 7 PM (for Wednesday)
    - Thursday 7 PM to Friday 7 PM (for Friday)
    - Saturday 10 AM to Sunday 10 AM (for Sunday)

    Args:
        day (str): The day to check (Wednesday, Friday, or Sunday).

    Returns:
        bool: True if the current time is within the window, False otherwise.
    """
    la_tz = pytz.timezone("America/Los_Angeles")
    now = datetime.now().astimezone(la_tz)
    weekday_index = now.weekday()  # Monday = 0, Sunday = 6
    hour = now.hour

    # Map weekday index (int) to DaysOfWeek enum
    weekday_enum = list(DaysOfWeek)[weekday_index]

    try:
        day_enum = DaysOfWeek(day.capitalize())
    except ValueError:
        return False  # Invalid day passed in

    if day_enum == DaysOfWeek.WEDNESDAY:
        return (weekday_enum == DaysOfWeek.TUESDAY and hour >= 19) or (
            weekday_enum == DaysOfWeek.WEDNESDAY and hour < 19
        )

    if day_enum == DaysOfWeek.FRIDAY:
        return (weekday_enum == DaysOfWeek.THURSDAY and hour >= 19) or (
            weekday_enum == DaysOfWeek.FRIDAY and hour < 19
        )

    if day_enum == DaysOfWeek.SUNDAY:
        return (weekday_enum == DaysOfWeek.SATURDAY and hour >= 10) or (
            weekday_enum == DaysOfWeek.SUNDAY and hour < 10
        )

    return False


def get_next_date_str(day: DaysOfWeekNumber) -> str:
    """
    Gets the next `day` and returns it in mm/dd form.

    Args:
        day (DaysOfWeekNumber): The day of the week to find the next date for.

    Returns:
        str: The formatted date string (mm/dd).
    """
    today = datetime.today()
    days_ahead = (day - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # Skip to next day if `day` is current day

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
    today = datetime.today()
    days_ahead = (day_num - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # Skip to next day if `day` is current day

    # The key change is here: we convert the final datetime object to a date object
    return (today + timedelta(days=days_ahead)).date()


def get_last_sunday() -> datetime:
    """
    Calculates the date of the last Sunday.

    Returns:
        datetime: The datetime object for the last Sunday.
    """
    now = datetime.now()
    days_to_subtract = (now.weekday() + 1) % 7
    if days_to_subtract == 0:
        days_to_subtract = 7
    return now - timedelta(days=days_to_subtract)


def is_active_hours() -> bool:
    """
    Check if current time is within active hours (7 AM - 1 AM Pacific).

    Active hours: 7:00 AM through 12:59 AM (i.e. hour >= 7 or hour < 1).
    Off-hours: 1:00 AM through 6:59 AM.

    Returns:
        True if within active hours, False otherwise.
    """
    la_tz = pytz.timezone("America/Los_Angeles")
    hour = datetime.now().astimezone(la_tz).hour
    return hour >= 7 or hour < 1


def is_ride_cycle_active() -> bool:
    """
    Check if the current time is within the ask-rides "sent this week" window.

    The window opens Wednesday at noon (when messages go out) and closes at
    end of Sunday. Monday and Tuesday (and Wednesday before noon) are outside
    the window because the new cycle has not started yet.

    Returns:
        True from Wednesday 12:00 PM through Sunday 11:59 PM, False otherwise.
    """
    now = datetime.now()
    return (now.weekday() == 2 and now.hour >= 12) or (3 <= now.weekday() <= 6)


def get_current_cycle_start() -> datetime:
    """
    Return the start of the current ask-rides cycle: the most recent Wednesday at noon.

    On Monday or Tuesday the new cycle has not started, so this steps back to
    the previous week's Wednesday.

    Returns:
        datetime of the most recent Wednesday at 12:00:00.
    """
    now = datetime.now()
    days_since_wednesday = (now.weekday() - 2) % 7
    if now.weekday() < 2:  # Monday or Tuesday — back to previous cycle
        days_since_wednesday += 7
    week_start = now - timedelta(days=days_since_wednesday)
    return week_start.replace(hour=12, minute=0, second=0, microsecond=0)


def get_send_wednesday(event_date: date) -> date:
    """
    Calculate the Wednesday send-day before an event date.

    Args:
        event_date: The event date (a Friday or Sunday).

    Returns:
        The Wednesday immediately before the event date.
    """
    days_to_subtract = (event_date.weekday() - 2) % 7
    if days_to_subtract == 0 and event_date.weekday() != 2:
        days_to_subtract = 7
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
        ("friday" in content and is_in_ride_day_window(DaysOfWeek.FRIDAY))
        or ("sunday" in content and is_in_ride_day_window(DaysOfWeek.SUNDAY))
        or ("wednesday" in content and is_in_ride_day_window(DaysOfWeek.WEDNESDAY))
    )


def get_next_wednesday_noon() -> datetime:
    """
    Return the next Wednesday at 12:00:00 (the next ask-rides send time).

    If today is Wednesday before noon, returns today at noon.
    If today is Wednesday at or after noon, returns next Wednesday at noon.

    Returns:
        datetime of the next ask-rides send time.
    """
    now = datetime.now()
    days_until_wednesday = (2 - now.weekday()) % 7
    if days_until_wednesday == 0 and now.hour >= 12:
        days_until_wednesday = 7
    next_run = now + timedelta(days=days_until_wednesday)
    return next_run.replace(hour=12, minute=0, second=0, microsecond=0)
