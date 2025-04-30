# cogs/job_scheduler.py

from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs.retreat_sync_roles import run_csv_job

class JobScheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

        # Register all jobs
        self.scheduler.add_job(
            run_csv_job,
            CronTrigger(hour=21, minute=00),  # 10 PM daily
            id="csv_job",
            args=[bot]
        )

        self.scheduler.start()

    def cog_unload(self):
        self.scheduler.shutdown()

async def setup(bot):
    await bot.add_cog(JobScheduler(bot))
