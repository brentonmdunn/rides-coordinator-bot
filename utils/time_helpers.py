import pytz
from datetime import datetime
from enums import DayOfWeek


def is_during_target_window(day: str) -> bool:
    """Checks if the current time in LA is within:
    - Thursday 7 PM to Friday 7 PM
    - Saturday 10 AM to Sunday 10 AM
    """
    LA_TZ = pytz.timezone("America/Los_Angeles")
    now = datetime.now().astimezone(LA_TZ)
    weekday_index = now.weekday()  # Monday = 0, Sunday = 6
    hour = now.hour

    # Map weekday index (int) to DayOfWeek enum
    weekday_enum = list(DayOfWeek)[weekday_index]

    try:
        day_enum = DayOfWeek(day.capitalize())
    except ValueError:
        return False  # Invalid day passed in

    if day_enum == DayOfWeek.FRIDAY:
        return (weekday_enum == DayOfWeek.THURSDAY and hour >= 19) or (
            weekday_enum == DayOfWeek.FRIDAY and hour < 19
        )

    if day_enum == DayOfWeek.SUNDAY:
        return (weekday_enum == DayOfWeek.SATURDAY and hour >= 10) or (
            weekday_enum == DayOfWeek.SUNDAY and hour < 10
        )

    return False
