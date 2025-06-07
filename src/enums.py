from enum import StrEnum, IntEnum


class ChannelIds(IntEnum):
    """
    Enum that contains channel IDs.
    In the format <CATEGORY>__<CHANNEL NAME>.
    """

    SERVING__LEADERSHIP = 1155357301050449931
    SERVING__DRIVER_CHAT_WOOOOO = 1286925673004269601
    SERVING__SUNDAY_SERVICE = 1286942023894433833
    BOT_STUFF__BOTS = 916823070017204274
    BOT_STUFF__BOT_SPAM_2 = 1208264072638898217
    REFERENCES__RIDES_ANNOUNCEMENTS = 939950319721406464
    SERVING__DRIVER_BOT_SPAM = 1297323073594458132
    BOT_STUFF__BOT_LOGS = 1208482668820570162
    SERVING__RETREAT_BOT_SPAM = 1366960392483377202


class DaysOfWeek(StrEnum):
    """Enum for consistent case for days of the week."""

    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


class DaysOfWeekNumber(IntEnum):
    """Enum for consistent case for days of the week."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class RoleIds(IntEnum):
    DRIVER = 1286924999730663454
    RIDES = 940467850261450752
