from datetime import datetime, timedelta
import pytz

from enums import DaysOfWeek, DaysOfWeekNumber


def is_during_target_window(day: str) -> bool:
    """Checks if the current time in LA is within:
    - Thursday 7 PM to Friday 7 PM
    - Saturday 10 AM to Sunday 10 AM
    """
    LA_TZ = pytz.timezone("America/Los_Angeles")
    now = datetime.now().astimezone(LA_TZ)
    weekday_index = now.weekday()  # Monday = 0, Sunday = 6
    hour = now.hour

    # Map weekday index (int) to DaysOfWeek enum
    weekday_enum = list(DaysOfWeek)[weekday_index]

    try:
        day_enum = DaysOfWeek(day.capitalize())
    except ValueError:
        return False  # Invalid day passed in

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
    today = datetime.today()
    days_ahead = (day - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # Skip to next day if `day` is current day

    next_friday = today + timedelta(days=days_ahead)
    formatted_date = next_friday.strftime("%-m/%-d")
    return formatted_date
