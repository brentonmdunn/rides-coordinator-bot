"""Live-rescheduling control for running APScheduler jobs."""

import logging
from typing import TYPE_CHECKING, cast

from apscheduler.triggers.cron import CronTrigger

from bot.core.bot_instance import get_bot
from bot.utils.time_helpers import LA_TZ

if TYPE_CHECKING:
    from bot.cogs.job_scheduler import JobScheduler

logger = logging.getLogger(__name__)


def reschedule_job(job_id: str, *, day_of_week: int, hour: int, minute: int) -> bool:
    """
    Reschedule a running APScheduler job to a new day/time.

    Args:
        job_id: The APScheduler job ID to reschedule.
        day_of_week: 0=Monday .. 6=Sunday (matches DaysOfWeekNumber).
        hour: Hour of day (0-23).
        minute: Minute of hour (0-59).

    Returns:
        True if the reschedule was applied live, False if the bot/scheduler
        isn't up yet (the caller should surface this as a non-blocking warning).
    """
    bot = get_bot()
    if bot is None:
        logger.warning("Cannot reschedule %s — bot not ready", job_id)
        return False

    raw_cog = bot.get_cog("JobScheduler")
    if raw_cog is None:
        logger.warning("Cannot reschedule %s — JobScheduler cog not loaded", job_id)
        return False
    cog = cast("JobScheduler", raw_cog)

    cog.scheduler.reschedule_job(
        job_id,
        trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=LA_TZ),
    )
    return True
