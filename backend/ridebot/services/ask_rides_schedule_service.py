"""
Service layer for the editable ask-rides send schedule.

Owns the unit of work (opens its own sessions) and the fallback logic: DB
customizations are merged over `DEFAULT_SCHEDULE`, and any DB failure falls
back to the hardcoded defaults so a scheduled job is never left unscheduled.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import OperationalError

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AskRidesScheduleSlot, CacheNamespace, JobName
from bot.core.messages_broadcaster import publish
from bot.core.scheduler_control import reschedule_job
from bot.repositories.ask_rides_schedule_repository import AskRidesScheduleRepository
from bot.utils.ask_rides_schedule_defaults import (
    ALLOWED_DAYS,
    DEFAULT_SCHEDULE,
    JOB_NAME_TO_SLOT,
    SCHEDULE_MAX_HOUR,
    SCHEDULE_MAX_MINUTE,
    SCHEDULE_MIN_HOUR,
    SCHEDULE_MIN_MINUTE,
    SLOT_TO_JOB_ID,
    ScheduleDefault,
)
from bot.utils.cache import invalidate_namespace
from bot.utils.constants import DAYS_IN_WEEK
from bot.utils.time_helpers import LA_TZ

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectiveSchedule:
    """A day/time schedule for one slot plus whether it's a saved customization."""

    day_of_week: int
    hour: int
    minute: int
    is_customized: bool


def _to_effective(default: ScheduleDefault, *, is_customized: bool) -> EffectiveSchedule:
    return EffectiveSchedule(
        day_of_week=default.day_of_week,
        hour=default.hour,
        minute=default.minute,
        is_customized=is_customized,
    )


class AskRidesScheduleService:
    """Handles reads/writes/live-rescheduling of the ask-rides send schedule."""

    @staticmethod
    async def get_effective_schedule(slot: AskRidesScheduleSlot) -> EffectiveSchedule:
        """
        Return the effective schedule for one slot.

        Never raises — any DB failure (including a missing table) falls back
        to the hardcoded default and logs the exception. Job startup wiring
        depends on this never failing.
        """
        default = _to_effective(DEFAULT_SCHEDULE[slot], is_customized=False)
        try:
            async with AsyncSessionLocal() as session:
                row = await AskRidesScheduleRepository.get(session, slot)
        except OperationalError:
            logger.exception(
                "DB error (likely missing table) fetching ask-rides schedule for %s; "
                "falling back to default",
                slot,
            )
            return default
        except Exception:
            logger.exception(
                "Unexpected error fetching ask-rides schedule for %s; falling back to default",
                slot,
            )
            return default

        if row is None:
            return default

        return EffectiveSchedule(
            day_of_week=row.day_of_week,
            hour=row.hour,
            minute=row.minute,
            is_customized=True,
        )

    @staticmethod
    async def get_effective_schedules() -> dict[AskRidesScheduleSlot, EffectiveSchedule]:
        """Return the effective schedule for every slot at once."""
        defaults = {
            slot: _to_effective(default, is_customized=False)
            for slot, default in DEFAULT_SCHEDULE.items()
        }

        try:
            async with AsyncSessionLocal() as session:
                rows = await AskRidesScheduleRepository.get_all(session)
        except Exception:
            logger.exception("Failed to load ask-rides schedules; using defaults")
            return defaults

        effective = dict(defaults)
        for row in rows:
            try:
                slot = AskRidesScheduleSlot(row.slot)
            except ValueError:
                logger.warning("Unknown ask-rides schedule slot in DB: %s", row.slot)
                continue
            effective[slot] = EffectiveSchedule(
                day_of_week=row.day_of_week,
                hour=row.hour,
                minute=row.minute,
                is_customized=True,
            )
        return effective

    @staticmethod
    def _validate(slot: AskRidesScheduleSlot, day_of_week: int, hour: int, minute: int) -> None:
        """Validate a schedule before saving. Raises ValueError on any violation."""
        if day_of_week not in ALLOWED_DAYS[slot]:
            allowed_names = sorted(ALLOWED_DAYS[slot])
            raise ValueError(
                f"day_of_week must be one of {allowed_names} for {slot.value}, got {day_of_week}"
            )

        if not (0 <= hour <= 23):
            raise ValueError(f"hour must be between 0 and 23, got {hour}")
        if not (0 <= minute <= 59):
            raise ValueError(f"minute must be between 0 and 59, got {minute}")

        time_minutes = hour * 60 + minute
        min_minutes = SCHEDULE_MIN_HOUR * 60 + SCHEDULE_MIN_MINUTE
        max_minutes = SCHEDULE_MAX_HOUR * 60 + SCHEDULE_MAX_MINUTE
        if not (min_minutes <= time_minutes <= max_minutes):
            raise ValueError(
                f"time must be between {SCHEDULE_MIN_HOUR:02d}:{SCHEDULE_MIN_MINUTE:02d} and "
                f"{SCHEDULE_MAX_HOUR:02d}:{SCHEDULE_MAX_MINUTE:02d}, got {hour:02d}:{minute:02d}"
            )

    @staticmethod
    async def update_schedule(
        slot: AskRidesScheduleSlot,
        day_of_week: int,
        hour: int,
        minute: int,
        updated_by: str,
    ) -> tuple[EffectiveSchedule, bool]:
        """
        Validate and save a customized schedule, apply it live, and broadcast an SSE update.

        Raises ValueError on validation failure (caller should turn this into a 422).

        Returns:
            A tuple of (effective schedule, whether the live reschedule was applied).
        """
        AskRidesScheduleService._validate(slot, day_of_week, hour, minute)

        async with AsyncSessionLocal() as session:
            row = await AskRidesScheduleRepository.upsert(
                session, slot, day_of_week, hour, minute, updated_by
            )

        applied = reschedule_job(
            SLOT_TO_JOB_ID[slot], day_of_week=day_of_week, hour=hour, minute=minute
        )

        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
        await publish({"type": "schedule_updated", "slot": slot.value})

        return (
            EffectiveSchedule(
                day_of_week=row.day_of_week,
                hour=row.hour,
                minute=row.minute,
                is_customized=True,
            ),
            applied,
        )

    @staticmethod
    async def reset_schedule(slot: AskRidesScheduleSlot) -> tuple[EffectiveSchedule, bool]:
        """
        Delete the saved customization for a slot, reschedule to the default, and
        broadcast an SSE update.

        Returns:
            A tuple of (effective schedule, whether the live reschedule was applied).
        """
        async with AsyncSessionLocal() as session:
            await AskRidesScheduleRepository.delete(session, slot)

        default = DEFAULT_SCHEDULE[slot]
        applied = reschedule_job(
            SLOT_TO_JOB_ID[slot],
            day_of_week=default.day_of_week,
            hour=default.hour,
            minute=default.minute,
        )

        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
        await publish({"type": "schedule_updated", "slot": slot.value})

        return _to_effective(default, is_customized=False), applied

    @staticmethod
    async def get_send_day_for_job(job_name: JobName) -> int:
        """
        Return the configured send day-of-week for the schedule slot governing *job_name*.

        Used by pause auto-resume logic, which needs to know which day the
        send happens on without hardcoding Wednesday.
        """
        slot = JOB_NAME_TO_SLOT[job_name]
        effective = await AskRidesScheduleService.get_effective_schedule(slot)
        return effective.day_of_week


async def get_next_schedule_occurrence(slot: AskRidesScheduleSlot) -> datetime:
    """
    Return the next LA-aware datetime this slot's configured schedule will fire.

    Reads the effective schedule (DB customization merged over the hardcoded
    default) and computes the next matching day/time. If today is the
    configured day but the time has already passed, rolls forward to next
    week — mirroring the old `get_next_monday_11am`/`get_next_wednesday_noon`
    behavior, just schedule-aware instead of hardcoded.

    This is the single source of truth for "next run" display, backing both
    the dashboard and (indirectly, via the same effective-schedule read) the
    real APScheduler trigger.
    """
    effective = await AskRidesScheduleService.get_effective_schedule(slot)
    now = datetime.now(tz=LA_TZ)
    days_ahead = (effective.day_of_week - now.weekday()) % DAYS_IN_WEEK
    candidate = now + timedelta(days=days_ahead)
    candidate = candidate.replace(
        hour=effective.hour, minute=effective.minute, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += timedelta(days=DAYS_IN_WEEK)
    return candidate


async def has_send_time_passed(slot: AskRidesScheduleSlot) -> bool:
    """
    Return True if `now` is at/after this week's configured send datetime for *slot*.

    Replaces the fixed-window `is_ride_cycle_active()` with a schedule-aware
    check: "has this slot already sent (or should have sent) this week?"
    """
    effective = await AskRidesScheduleService.get_effective_schedule(slot)
    now = datetime.now(tz=LA_TZ)
    send_minutes = effective.hour * 60 + effective.minute
    now_minutes = now.hour * 60 + now.minute

    if now.weekday() == effective.day_of_week:
        return now_minutes >= send_minutes
    return now.weekday() > effective.day_of_week
