"""
jobs/temp_drivers.py

Scheduled job that sweeps expired temporary Driver role grants.
"""

import logging

from discord.ext.commands import Bot

from ridebot.services.temp_driver_service import TempDriverService
from shared.core.enums import FeatureFlagNames
from shared.core.logger import log_job_quiet
from shared.utils.checks import bot_enabled, feature_flag_enabled

logger = logging.getLogger(__name__)


@log_job_quiet
@bot_enabled
@feature_flag_enabled(FeatureFlagNames.TEMP_DRIVER_EXPIRY_JOB, enable_logs=False)
async def run_temp_driver_expiry(bot: Bot) -> None:
    """Runner for the temporary Driver role expiry sweep."""
    await TempDriverService(bot).expire_due()
