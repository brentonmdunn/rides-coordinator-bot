# cogs/job_scheduler.py

from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs.retreat_sync_roles import run_csv_job
from jobs.ask_rides import run_ask_rides_fri, run_ask_rides_sun, run_ask_rides_sun_class


class JobScheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

        # Register all jobs
        self.scheduler.add_job(
            run_csv_job,
            CronTrigger(hour=21, minute=00),
            id="csv_job",
            args=[bot],
        )

        self.scheduler.add_job(
            run_ask_rides_fri,
            CronTrigger(day_of_week="wed", hour=16, minute=00),
            id="run_ask_rides_fri",
            args=[bot],
        )

        self.scheduler.add_job(
            run_ask_rides_sun,
            CronTrigger(day_of_week="sat", hour=10, minute=00),
            id="run_ask_rides_sun",
            args=[bot],
        )

        self.scheduler.add_job(
            run_ask_rides_sun_class,
            CronTrigger(day_of_week="sat", hour=10, minute=1),
            id="run_ask_rides_sun_class",
            args=[bot],
        )

        self.scheduler.start()

    def cog_unload(self):
        self.scheduler.shutdown()


async def setup(bot):
    await bot.add_cog(JobScheduler(bot))
