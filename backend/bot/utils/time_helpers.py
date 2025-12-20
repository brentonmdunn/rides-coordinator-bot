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


def is_during_target_window(day: str) -> bool:
    """Checks if the current time in LA is within the target window for the given day.

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


def get_next_date(day: DaysOfWeekNumber) -> str:
    """Gets the next `day` and returns it in mm/dd form.

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
    """Gets the next `day` as a date object.

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
