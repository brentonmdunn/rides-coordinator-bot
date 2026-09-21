"""Cog for scheduling StonesBot's background jobs."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from discord.ext import commands

from shared.core.enums import ChannelIds
from shared.utils.constants import LA_TZ
from stonesbot.jobs.weekly_events import run_weekly_events_announcement

logger = logging.getLogger(__name__)

WEEKLY_EVENTS_DAY_OF_WEEK = "sun"
WEEKLY_EVENTS_HOUR = 12
WEEKLY_EVENTS_MINUTE = 0


class StonesJobScheduler(commands.Cog):
    """Cog that manages StonesBot's scheduled tasks using APScheduler."""

    def __init__(self, bot: commands.Bot):
        """
        Initialize the StonesJobScheduler cog.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot
        # Pin the scheduler's timezone explicitly — otherwise cron fires in the
        # container's OS timezone rather than LA time.
        self.scheduler = AsyncIOScheduler(timezone=LA_TZ)

        self.scheduler.add_job(
            run_weekly_events_announcement,
            CronTrigger(
                day_of_week=WEEKLY_EVENTS_DAY_OF_WEEK,
                hour=WEEKLY_EVENTS_HOUR,
                minute=WEEKLY_EVENTS_MINUTE,
                timezone=LA_TZ,
            ),
            id="run_weekly_events_announcement",
            args=[bot, ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS],
        )

        self.scheduler.start()

    def cog_unload(self):
        """Shuts down the scheduler when the cog is unloaded."""
        self.scheduler.shutdown()


async def setup(bot):
    """Sets up the StonesJobScheduler cog."""
    await bot.add_cog(StonesJobScheduler(bot))
