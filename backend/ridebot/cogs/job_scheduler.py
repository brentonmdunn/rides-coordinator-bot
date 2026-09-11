"""Cog for scheduling background jobs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

from bot.core.enums import AskRidesScheduleSlot, ChannelIds

# from jobs_disabled.retreat_sync_roles import run_csv_job
from bot.jobs.ask_rides import (
    run_ask_rides_all,
    run_ask_rides_wed,
    run_periodic_cache_warming,
)
from bot.jobs.sync_rides_locations import sync_rides_locations
from bot.services.ask_rides_schedule_service import AskRidesScheduleService, EffectiveSchedule
from bot.utils.ask_rides_schedule_defaults import DEFAULT_SCHEDULE
from bot.utils.time_helpers import LA_TZ

logger = logging.getLogger(__name__)


class JobScheduler(commands.Cog):
    """Cog that manages scheduled tasks using APScheduler."""

    def __init__(
        self,
        bot,
        wed_schedule: EffectiveSchedule,
        fri_sun_schedule: EffectiveSchedule,
    ):
        """
        Initialize the JobScheduler cog.

        Args:
            bot: The Discord bot instance.
            wed_schedule: Effective schedule for the Wednesday-fellowship reminder slot.
            fri_sun_schedule: Effective schedule for the Friday/Sunday group slot.
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

        self.scheduler.add_job(
            sync_rides_locations,
            CronTrigger(hour=3, minute=0),
            id="sync_rides_locations",
        )

        # self.scheduler.add_job(
        #     delete_past_pickups,
        #     CronTrigger(day_of_week="mon", hour=3, minute=0),
        #     id="delete_past_pickups",
        # )

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

    await bot.add_cog(JobScheduler(bot, wed_schedule, fri_sun_schedule))
