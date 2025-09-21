"""jobs/ask_rides.py

Scheduled jobs for asking for rides.
"""

import discord
from discord.abc import Messageable
from discord.ext.commands import Bot

from app.core.enums import ChannelIds, DaysOfWeekNumber, FeatureFlagNames, RoleIds
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled
from app.utils.format_message import ping_channel, ping_role, ping_role_with_message
from app.utils.time_helpers import get_next_date

WILDCARD_DATES: list[str] = ["6/20", "6/27", "6/29"]
CLASS_DATES: list[str] = []


def _make_wednesday_msg() -> str | None:
    """Create message for Wednesday rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.WEDNESDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React if you need a ride for Wednesday night Bible study {formatted_date} "
        "(leave between 7 and 7:10pm)!"
    )


def _make_friday_msg() -> str | None:
    """Create message for Friday rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.FRIDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React if you need a ride for Friday night fellowship {formatted_date} "
        "(leave between 7 and 7:10pm)!"
    )


def _make_sunday_msg() -> str | None:
    """Create message for Sunday service rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.SUNDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React if you need a ride for Sunday service {formatted_date} (leave between 10 and 10:10 am)!\n\n"  # noqa
        "🍔 = ride to church, lunch, and back to campus/apt (arrive back ~2:30pm)\n"
        "🏠 = ride to church and leave back to campus/apt before lunch (arrive back ~1:00pm)\n"
        "➡️ = only need ride to church\n"
        "⬅️ = only need ride to lunch and back to campus/apt\n"
        f"✳️ = something else (please ping {ping_role(RoleIds.RIDE_COORDINATOR)} in {ping_channel(ChannelIds.REFERENCES__RIDES_GENERAL)})"  # noqa
    )


def _make_sunday_msg_class() -> str | None:
    """Create message for Sunday class rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.SUNDAY)
    if formatted_date in WILDCARD_DATES or formatted_date not in CLASS_DATES:
        return None
    return (
        f"React if you need a ride to Bible Theology Class on Sunday {formatted_date} "
        "(leave between 8:30 and 8:40 am)"
    )


def _format_message(message: str) -> str:
    """Adds @Rides to message."""
    return ping_role_with_message(RoleIds.RIDES, message)


async def _ask_rides_template(bot: Bot, make_message: callable) -> discord.Message | None:
    """
    Helper method for ask rides jobs.
    """
    channel: Messageable | None = bot.get_channel(
        ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
    )
    if not channel:
        logger.info("Error channel not found")
        return
    message: str | None = make_message()
    if message is None:
        return
    return await channel.send(
        _format_message(message),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )


@feature_flag_enabled(FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB)
async def run_ask_rides_wed(bot: Bot) -> None:
    """Runner for Wednesday rides message."""
    await _ask_rides_template(bot, _make_wednesday_msg)


@feature_flag_enabled(FeatureFlagNames.ASK_FRIDAY_RIDES_JOB)
async def run_ask_rides_fri(bot: Bot) -> None:
    """Runner for Friday rides message."""
    await _ask_rides_template(bot, _make_friday_msg)


@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_RIDES_JOB)
async def run_ask_rides_sun(bot: Bot) -> None:
    """Runner for Sunday service rides message."""
    sent_message = await _ask_rides_template(bot, _make_sunday_msg)
    reactions = ["🍔", "🏠", "➡️", "⬅️", "✳️"]
    for emoji in reactions:
        await sent_message.add_reaction(emoji)


async def run_ask_rides_sun_class(bot: Bot) -> None:
    """Runner for Sunday class rides message."""
    await _ask_rides_template(bot, _make_sunday_msg_class)
