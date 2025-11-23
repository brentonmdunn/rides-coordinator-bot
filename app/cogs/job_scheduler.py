"""Cog for scheduling background jobs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

from app.core.enums import ChannelIds

# from jobs_disabled.retreat_sync_roles import run_csv_job
from app.jobs.ask_rides import (
    run_ask_rides_all,
)
from app.jobs.sync_rides_locations import sync_rides_locations


class JobScheduler(commands.Cog):
    """Cog that manages scheduled tasks using APScheduler."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

        # # Register all jobs
        # self.scheduler.add_job(
        #     run_csv_job,
        #     CronTrigger(hour=21, minute=00),
        #     id="csv_job",
        #     args=[bot],
        # )

        self.scheduler.add_job(
            run_ask_rides_all,
            CronTrigger(day_of_week="wed", hour=12, minute=0),
            id="run_ask_rides_all",
            args=[bot, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS],
        )

        # self.scheduler.add_job(
        #     run_ask_rides_fri,
        #     CronTrigger(day_of_week="wed", hour=12, minute=0),
        #     id="run_ask_rides_fri",
        #     args=[bot],
        # )

        # self.scheduler.add_job(
        #     run_ask_rides_wed,
        #     CronTrigger(day_of_week="mon", hour=16, minute=0),
        #     id="run_ask_rides_wed",
        #     args=[bot],
        # )

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

    def cog_unload(self) -> None:
        """Shuts down the scheduler when the cog is unloaded."""
        self.scheduler.shutdown()


async def setup(bot):
    """Sets up the JobScheduler cog."""
    await bot.add_cog(JobScheduler(bot))
