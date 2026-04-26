"""Cog for scheduling background jobs."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

from bot.core.enums import ChannelIds
from bot.jobs.ask_rides import (
    run_ask_rides_all,
    run_periodic_cache_warming,
)
from bot.jobs.non_discord_rides import delete_past_pickups
from bot.jobs.sync_rides_locations import sync_rides_locations


class JobScheduler(commands.Cog):
    """Cog that manages scheduled tasks using APScheduler."""

    def __init__(self, bot):
        """Initialize the JobScheduler cog."""
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

        self.scheduler.add_job(
            run_ask_rides_all,
            CronTrigger(day_of_week="wed", hour=12, minute=0),
            id="run_ask_rides_all",
            args=[bot, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS],
        )

        self.scheduler.add_job(
            run_periodic_cache_warming,
            CronTrigger(minute="*/30"),
            id="run_periodic_cache_warming",
            args=[bot],
        )

        self.scheduler.add_job(
            sync_rides_locations,
            CronTrigger(hour=3, minute=0),
            id="sync_rides_locations",
        )

        self.scheduler.add_job(
            delete_past_pickups,
            CronTrigger(day_of_week="mon", hour=3, minute=0),
            id="delete_past_pickups",
        )

        self.scheduler.start()

    def cog_unload(self):
        """Shuts down the scheduler when the cog is unloaded."""
        self.scheduler.shutdown()


async def setup(bot):
    """Sets up the JobScheduler cog."""
    await bot.add_cog(JobScheduler(bot))
