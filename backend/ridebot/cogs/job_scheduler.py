"""Cog for scheduling background jobs."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord.ext import commands

# from jobs_disabled.retreat_sync_roles import run_csv_job
from ridebot.jobs.ask_rides import (
    run_ask_rides_all,
    run_ask_rides_wed,
    run_periodic_cache_warming,
)
from ridebot.jobs.pickups_summary import run_friday_pickups_summary, run_sunday_pickups_summary
from ridebot.jobs.temp_drivers import run_temp_driver_expiry
from ridebot.services.ask_rides_schedule_service import AskRidesScheduleService, EffectiveSchedule
from ridebot.services.pickup_summary_service import (
    EffectivePickupSummarySetting,
    PickupSummaryService,
)
from ridebot.utils.ask_rides_schedule_defaults import DEFAULT_SCHEDULE
from ridebot.utils.constants import TEMP_DRIVER_EXPIRY_JOB_ID, TEMP_DRIVER_SWEEP_MINUTES
from ridebot.utils.pickup_summary_defaults import DEFAULT_SUMMARY_SCHEDULE, SUMMARY_SLOT_TO_JOB_ID
from ridebot.utils.time_helpers import LA_TZ
from shared.core.enums import AskRidesScheduleSlot, ChannelIds, PickupSummarySlot
from shared.core.logger import QuietJobFilter

logger = logging.getLogger(__name__)

# APScheduler's own "running/executed" INFO lines for the temp-driver sweep are
# noise (it ticks every few minutes and almost always finds nothing) — guard
# against adding this filter twice if the cog is reloaded.
_apscheduler_executor_logger = logging.getLogger("apscheduler.executors.default")
if not any(isinstance(f, QuietJobFilter) for f in _apscheduler_executor_logger.filters):
    _apscheduler_executor_logger.addFilter(QuietJobFilter({TEMP_DRIVER_EXPIRY_JOB_ID}))


class JobScheduler(commands.Cog):
    """Cog that manages scheduled tasks using APScheduler."""

    def __init__(
        self,
        bot,
        wed_schedule: EffectiveSchedule,
        fri_sun_schedule: EffectiveSchedule,
        summary_settings: dict[PickupSummarySlot, EffectivePickupSummarySetting],
    ):
        """
        Initialize the JobScheduler cog.

        Args:
            bot: The Discord bot instance.
            wed_schedule: Effective schedule for the Wednesday-fellowship reminder slot.
            fri_sun_schedule: Effective schedule for the Friday/Sunday group slot.
            summary_settings: Effective day/time for each pickup-summary slot. The job is
                always registered here; the enabled toggle is checked at run time.
        """
        self.bot = bot
        # Pin the scheduler's timezone explicitly — otherwise cron fires in the
        # container's OS timezone rather than LA time.
        self.scheduler = AsyncIOScheduler(timezone=LA_TZ)

        # # Register all jobs
        # self.scheduler.add_job(
        #     run_csv_job,
        #     CronTrigger(hour=21, minute=00),
        #     id="csv_job",
        #     args=[bot],
        # )

        self.scheduler.add_job(
            run_ask_rides_all,
            CronTrigger(
                day_of_week=fri_sun_schedule.day_of_week,
                hour=fri_sun_schedule.hour,
                minute=fri_sun_schedule.minute,
                timezone=LA_TZ,
            ),
            id="run_ask_rides_all",
            args=[bot, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS],
        )

        self.scheduler.add_job(
            run_periodic_cache_warming,
            CronTrigger(minute="*/30"),
            id="run_periodic_cache_warming",
            args=[bot],
        )

        # self.scheduler.add_job(
        #     run_ask_rides_fri,
        #     CronTrigger(day_of_week="wed", hour=12, minute=0),
        #     id="run_ask_rides_fri",
        #     args=[bot],
        # )

        self.scheduler.add_job(
            run_ask_rides_wed,
            CronTrigger(
                day_of_week=wed_schedule.day_of_week,
                hour=wed_schedule.hour,
                minute=wed_schedule.minute,
                timezone=LA_TZ,
            ),
            id="run_ask_rides_wed",
            args=[bot],
        )

        # self.scheduler.add_job(
        #     run_ask_rides_sun,
        #     CronTrigger(day_of_week="fri", hour=23, minute=19),
        #     id="run_ask_rides_sun",
        #     args=[bot],
        # )

        # self.scheduler.add_job(
        #     run_ask_rides_sun_class,
        #     CronTrigger(day_of_week="wed", hour=16, minute=2),
        #     id="run_ask_rides_sun_class",
        #     args=[bot],
        # )

        # self.scheduler.add_job(
        #     delete_past_pickups,
        #     CronTrigger(day_of_week="mon", hour=3, minute=0),
        #     id="delete_past_pickups",
        # )

        for slot, job_func in (
            (PickupSummarySlot.FRIDAY, run_friday_pickups_summary),
            (PickupSummarySlot.SUNDAY, run_sunday_pickups_summary),
        ):
            setting = summary_settings[slot]
            self.scheduler.add_job(
                job_func,
                CronTrigger(
                    day_of_week=setting.day_of_week,
                    hour=setting.hour,
                    minute=setting.minute,
                    timezone=LA_TZ,
                ),
                id=SUMMARY_SLOT_TO_JOB_ID[slot],
                args=[bot],
            )

        self.scheduler.add_job(
            run_temp_driver_expiry,
            IntervalTrigger(minutes=TEMP_DRIVER_SWEEP_MINUTES),
            id=TEMP_DRIVER_EXPIRY_JOB_ID,
            args=[bot],
            next_run_time=datetime.now(LA_TZ),
        )

        self.scheduler.start()

    def cog_unload(self):
        """Shuts down the scheduler when the cog is unloaded."""
        self.scheduler.shutdown()


def _default_effective_schedule(slot: AskRidesScheduleSlot) -> EffectiveSchedule:
    """Build an EffectiveSchedule from the hardcoded default for *slot*."""
    default = DEFAULT_SCHEDULE[slot]
    return EffectiveSchedule(
        day_of_week=default.day_of_week,
        hour=default.hour,
        minute=default.minute,
        is_customized=False,
    )


def _default_effective_summary_setting(slot: PickupSummarySlot) -> EffectivePickupSummarySetting:
    """Build an EffectivePickupSummarySetting from the hardcoded default for *slot*."""
    default = DEFAULT_SUMMARY_SCHEDULE[slot]
    return EffectivePickupSummarySetting(
        enabled=True,
        day_of_week=default.day_of_week,
        hour=default.hour,
        minute=default.minute,
        is_customized=False,
    )


async def setup(bot):
    """
    Sets up the JobScheduler cog.

    Resolves the ask-rides send schedule (DB-customized or default) before
    constructing the cog, so the initial CronTrigger literals match whatever
    is currently configured instead of being hardcoded. `get_effective_schedule`
    already falls back to defaults on any DB error and never raises, but this
    is wrapped defensively anyway — a schedule-config problem must never
    prevent the bot from starting.
    """
    try:
        wed_schedule = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.WEDNESDAY_REMINDER
        )
        fri_sun_schedule = await AskRidesScheduleService.get_effective_schedule(
            AskRidesScheduleSlot.FRI_SUN_GROUP
        )
    except Exception:
        logger.exception(
            "Failed to load ask-rides schedule at startup; falling back to hardcoded defaults"
        )
        wed_schedule = _default_effective_schedule(AskRidesScheduleSlot.WEDNESDAY_REMINDER)
        fri_sun_schedule = _default_effective_schedule(AskRidesScheduleSlot.FRI_SUN_GROUP)

    try:
        summary_settings = await PickupSummaryService.get_effective_settings()
    except Exception:
        logger.exception(
            "Failed to load pickup summary settings at startup; falling back to hardcoded defaults"
        )
        summary_settings = {
            slot: _default_effective_summary_setting(slot) for slot in PickupSummarySlot
        }

    await bot.add_cog(JobScheduler(bot, wed_schedule, fri_sun_schedule, summary_settings))
