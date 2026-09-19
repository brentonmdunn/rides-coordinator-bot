"""
jobs/pickups_summary.py

Scheduled jobs that post the pickup-list summary to the ride coordinators channel.
"""

import logging

from discord.ext.commands import Bot

from ridebot.services.pickup_summary_service import PickupSummaryService
from ridebot.utils.pickup_summary_defaults import SUMMARY_SLOT_TO_FLAG
from shared.core.enums import PickupSummarySlot
from shared.core.logger import log_job
from shared.utils.checks import bot_enabled, feature_flag_enabled

logger = logging.getLogger(__name__)


@log_job
@bot_enabled
@feature_flag_enabled(SUMMARY_SLOT_TO_FLAG[PickupSummarySlot.FRIDAY])
async def run_friday_pickups_summary(bot: Bot) -> None:
    """Runner for the Friday pickup-list summary, posted to ride coordinators."""
    await PickupSummaryService(bot).send_summary(PickupSummarySlot.FRIDAY)


@log_job
@bot_enabled
@feature_flag_enabled(SUMMARY_SLOT_TO_FLAG[PickupSummarySlot.SUNDAY])
async def run_sunday_pickups_summary(bot: Bot) -> None:
    """Runner for the Sunday pickup-list summary, posted to ride coordinators."""
    await PickupSummaryService(bot).send_summary(PickupSummarySlot.SUNDAY)
