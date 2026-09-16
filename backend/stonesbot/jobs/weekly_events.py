"""Scheduled job that announces the coming week's events."""

import logging

import discord
from discord.ext.commands import Bot

from shared.core.enums import ChannelIds, FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_job
from shared.utils.checks import bot_enabled, feature_flag_enabled
from stonesbot.services.weekly_events_service import WeeklyEventsService

logger = logging.getLogger(__name__)


@log_job
@bot_enabled
@feature_flag_enabled(FeatureFlagNames.WEEKLY_EVENTS_ANNOUNCEMENT_JOB)
async def run_weekly_events_announcement(
    bot: Bot,
    channel_id: int = ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS,
) -> discord.Message | None:
    """
    Announce next week's events and delete the previous week's announcement.

    Scheduled for Sundays at 6PM LA time. Gated by StonesBot's kill switch and
    the `weekly_events_announcement_job` flag.

    Args:
        bot: The Discord bot instance.
        channel_id: The channel to announce in.

    Returns:
        The sent message, or None if nothing was sent.
    """
    try:
        return await WeeklyEventsService.post_weekly_announcement(bot, channel_id)
    except Exception as e:
        logger.exception("Weekly events announcement job failed")
        await send_error_to_discord("**Error** in `run_weekly_events_announcement`", error=e)
        return None
