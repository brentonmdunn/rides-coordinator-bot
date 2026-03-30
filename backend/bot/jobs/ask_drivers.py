import logging

import discord
from discord.abc import Messageable
from discord.ext.commands import Bot

from bot.api import send_error_to_discord
from bot.core.enums import (
    ChannelIds,
    DaysOfWeek,
    FeatureFlagNames,
    JobName,
)
from bot.core.logger import log_job
from bot.repositories.message_schedule_repository import MessageScheduleRepository
from bot.services.driver_service import DriverService
from bot.utils.checks import feature_flag_enabled

logger = logging.getLogger(__name__)


async def _ask_drivers_template(
    bot: Bot, message: str, emojis: list[str], channel_id=ChannelIds.SERVING__DRIVER_CHAT_WOOOOO
) -> discord.Message | None:
    channel: Messageable | None = bot.get_channel(channel_id)
    if not channel:
        logger.warning(f"Channel not found with ID: {channel_id}")
        return None

    try:
        sent_message = await channel.send(
            message, allowed_mentions=discord.AllowedMentions(roles=True)
        )
        for emoji in emojis:
            await sent_message.add_reaction(emoji)
        return sent_message
    except discord.HTTPException as e:
        logger.error(f"Failed to send message to channel {channel_id}: {e}")
        await send_error_to_discord(bot, e)
        return None


@log_job
@feature_flag_enabled(FeatureFlagNames.ASK_FRIDAY_DRIVERS_JOB)
async def run_ask_drivers_fri(bot: Bot, channel_id=ChannelIds.SERVING__DRIVER_CHAT_WOOOOO):
    """
    Send the Friday driver ask message to the driver chat channel.

    Skips sending if the Friday job is currently paused.
    """
    if await MessageScheduleRepository.is_job_paused(JobName.FRIDAY):
        logger.info("Blocking run_ask_drivers_fri - job is paused")
        return

    driver_service = DriverService()
    emojis = driver_service.get_emojis(DaysOfWeek.FRIDAY)
    message = driver_service.format_message("Friday felly")
    await _ask_drivers_template(bot, message, emojis, channel_id)


@log_job
@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_DRIVERS_JOB)
async def run_ask_drivers_sun(bot: Bot, channel_id=ChannelIds.SERVING__DRIVER_CHAT_WOOOOO):
    """
    Send the Sunday driver ask message to the driver chat channel.

    Skips sending if the Sunday job is paused or the ask-rides window is not active.
    """
    if await MessageScheduleRepository.is_job_paused(JobName.SUNDAY):
        logger.info("Blocking run_ask_drivers_sun - job is paused")
        return

    from bot.jobs.ask_rides import _should_send_ask_rides_sun

    if not _should_send_ask_rides_sun():
        logger.info("Blocking run_ask_drivers_sun - blocked by _should_send_ask_rides_sun()")
        return

    driver_service = DriverService()
    emojis = driver_service.get_emojis(DaysOfWeek.SUNDAY)
    message = driver_service.format_message("Sunday service")
    await _ask_drivers_template(bot, message, emojis, channel_id)
