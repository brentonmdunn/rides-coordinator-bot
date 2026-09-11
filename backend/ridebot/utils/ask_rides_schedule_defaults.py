"""Hardcoded defaults and validation rules for the ask-rides send schedule."""

from dataclasses import dataclass

from bot.core.enums import AskRidesScheduleSlot, DaysOfWeekNumber, JobName

# Daytime send window, inclusive. 22:00 is allowed, 22:30 is not.
SCHEDULE_MIN_HOUR = 6
SCHEDULE_MIN_MINUTE = 0
SCHEDULE_MAX_HOUR = 22
SCHEDULE_MAX_MINUTE = 0


@dataclass(frozen=True)
class ScheduleDefault:
    """A hardcoded default day/time for a schedule slot."""

    day_of_week: int
    hour: int
    minute: int


# Matches today's hardcoded CronTrigger literals in job_scheduler.py.
DEFAULT_SCHEDULE: dict[AskRidesScheduleSlot, ScheduleDefault] = {
    AskRidesScheduleSlot.WEDNESDAY_REMINDER: ScheduleDefault(
        day_of_week=DaysOfWeekNumber.MONDAY, hour=11, minute=0
    ),
    AskRidesScheduleSlot.FRI_SUN_GROUP: ScheduleDefault(
        day_of_week=DaysOfWeekNumber.WEDNESDAY, hour=12, minute=0
    ),
}

# Per-slot allowed send days — the send day must precede the first event the
# slot announces.
ALLOWED_DAYS: dict[AskRidesScheduleSlot, frozenset[int]] = {
    AskRidesScheduleSlot.WEDNESDAY_REMINDER: frozenset(
        {DaysOfWeekNumber.MONDAY, DaysOfWeekNumber.TUESDAY}
    ),
    AskRidesScheduleSlot.FRI_SUN_GROUP: frozenset(
        {
            DaysOfWeekNumber.MONDAY,
            DaysOfWeekNumber.TUESDAY,
            DaysOfWeekNumber.WEDNESDAY,
            DaysOfWeekNumber.THURSDAY,
        }
    ),
}

# Maps a schedule slot to the APScheduler job ID it controls.
SLOT_TO_JOB_ID: dict[AskRidesScheduleSlot, str] = {
    AskRidesScheduleSlot.WEDNESDAY_REMINDER: "run_ask_rides_wed",
    AskRidesScheduleSlot.FRI_SUN_GROUP: "run_ask_rides_all",
}

# Maps a pause-tracking JobName to the schedule slot that governs its send day.
# "friday"/"sunday"/"sunday_class" all send as part of the batched Fri/Sun group;
# "wednesday" is the standalone fellowship reminder.
JOB_NAME_TO_SLOT: dict[JobName, AskRidesScheduleSlot] = {
    JobName.WEDNESDAY: AskRidesScheduleSlot.WEDNESDAY_REMINDER,
    JobName.FRIDAY: AskRidesScheduleSlot.FRI_SUN_GROUP,
    JobName.SUNDAY: AskRidesScheduleSlot.FRI_SUN_GROUP,
    JobName.SUNDAY_CLASS: AskRidesScheduleSlot.FRI_SUN_GROUP,
}
