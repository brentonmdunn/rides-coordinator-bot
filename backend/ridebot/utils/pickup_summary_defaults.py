"""Hardcoded defaults and validation rules for the scheduled pickup-list summaries."""

from ridebot.utils.ask_rides_schedule_defaults import ScheduleDefault
from shared.core.enums import (
    DaysOfWeekNumber,
    FeatureFlagNames,
    JobName,
    PickupSummarySlot,
    RideOption,
)

# Daytime send window, inclusive — same bounds as the ask-rides schedule.
SUMMARY_MIN_HOUR = 6
SUMMARY_MIN_MINUTE = 0
SUMMARY_MAX_HOUR = 22
SUMMARY_MAX_MINUTE = 0

DEFAULT_SUMMARY_SCHEDULE: dict[PickupSummarySlot, ScheduleDefault] = {
    PickupSummarySlot.FRIDAY: ScheduleDefault(
        day_of_week=DaysOfWeekNumber.FRIDAY, hour=11, minute=0
    ),
    PickupSummarySlot.SUNDAY: ScheduleDefault(
        day_of_week=DaysOfWeekNumber.SATURDAY, hour=16, minute=0
    ),
}

# The summary must go out on or before the day of the event it lists pickups for.
SUMMARY_ALLOWED_DAYS: dict[PickupSummarySlot, frozenset[int]] = {
    PickupSummarySlot.FRIDAY: frozenset(
        {
            DaysOfWeekNumber.MONDAY,
            DaysOfWeekNumber.TUESDAY,
            DaysOfWeekNumber.WEDNESDAY,
            DaysOfWeekNumber.THURSDAY,
            DaysOfWeekNumber.FRIDAY,
        }
    ),
    PickupSummarySlot.SUNDAY: frozenset(
        {
            DaysOfWeekNumber.MONDAY,
            DaysOfWeekNumber.TUESDAY,
            DaysOfWeekNumber.WEDNESDAY,
            DaysOfWeekNumber.THURSDAY,
            DaysOfWeekNumber.FRIDAY,
            DaysOfWeekNumber.SATURDAY,
        }
    ),
}

# `?settings=` value the frontend uses to open Site Settings at the pickup summaries section.
PICKUP_SUMMARIES_SETTINGS_SECTION = "pickup-summaries"

# APScheduler job IDs.
SUMMARY_SLOT_TO_JOB_ID: dict[PickupSummarySlot, str] = {
    PickupSummarySlot.FRIDAY: "run_friday_pickups_summary",
    PickupSummarySlot.SUNDAY: "run_sunday_pickups_summary",
}

SUMMARY_SLOT_TO_FLAG: dict[PickupSummarySlot, FeatureFlagNames] = {
    PickupSummarySlot.FRIDAY: FeatureFlagNames.FRIDAY_PICKUPS_SUMMARY_JOB,
    PickupSummarySlot.SUNDAY: FeatureFlagNames.SUNDAY_PICKUPS_SUMMARY_JOB,
}

# The ask-rides job whose message (and pause state) each summary reads.
SUMMARY_SLOT_TO_JOB_NAME: dict[PickupSummarySlot, JobName] = {
    PickupSummarySlot.FRIDAY: JobName.FRIDAY,
    PickupSummarySlot.SUNDAY: JobName.SUNDAY,
}

# Mirrors /list-pickups-friday (no option) and /list-pickups-sunday.
SUMMARY_SLOT_TO_RIDE_OPTION: dict[PickupSummarySlot, RideOption | None] = {
    PickupSummarySlot.FRIDAY: None,
    PickupSummarySlot.SUNDAY: RideOption.SUNDAY_PICKUP,
}
