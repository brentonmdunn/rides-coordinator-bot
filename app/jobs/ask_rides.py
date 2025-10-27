"""jobs/ask_rides.py

Scheduled jobs for asking for rides.
"""

import os
from collections.abc import Callable

import discord
from discord.abc import Messageable
from discord.ext.commands import Bot

from app.cogs.feature_flags import feature_flag_status
from app.core.enums import ChannelIds, DaysOfWeekNumber, FeatureFlagNames, RoleIds
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled
from app.utils.format_message import ping_role_with_message, ping_user
from app.utils.time_helpers import get_next_date

WILDCARD_DATES: list[str] = ["6/20", "6/27", "6/29"]
CLASS_DATES: list[str] = []


def _make_wednesday_msg() -> str | None:
    """Create message for Wednesday rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.WEDNESDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React to this message if you need a ride for Wednesday night Bible study {formatted_date} "  # noqa
        "(leave between 7 and 7:10pm)!"
    )


def _make_friday_msg() -> str | None:
    """Create message for Friday rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.FRIDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React to this message if you need a ride for Friday night fellowship {formatted_date} "
        "(leave between 7 and 7:10pm)!"
    )


def _make_sunday_msg() -> str | None:
    """Create message for Sunday service rides."""
    formatted_date: str = get_next_date(DaysOfWeekNumber.SUNDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return (
        f"React to this message if you need a ride for Sunday service {formatted_date} (leave between 10 and 10:10am)!\n\n"  # noqa
        "🍔 = ride to church, lunch, and back to campus/apt (arrive back ~2:30pm)\n"
        "🏠 = ride to church and back to campus/apt (arrive back ~1:00pm)\n"
        f"✳️ = something else (please DM {ping_user(os.getenv('MAIN_RIDES_COORD_USER_ID'))})"
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



RIDE_TYPES_CONFIG = {
    "friday": {
        "title": "Rides to Friday Fellowship",
        "color": discord.Color.from_rgb(227, 132, 212),  # Pink/Magenta
    },
    "class": {"title": "Rides to Bible Theology Class", "color": discord.Color.blue()},
    "sunday": {
        "title": "Rides to Sunday Service",
        "color": discord.Color.from_rgb(3, 58, 145),  # Dark Blue
    },
}

DEFAULT_RIDE_TITLE = "Rides Announcement"
DEFAULT_RIDE_COLOR = discord.Color.default()


async def _ask_rides_template(
    bot: Bot,
    make_message: Callable[[], str | None],  # More specific type hint
    channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
) -> discord.Message | None:
    """
    Helper method for ask rides jobs.
    """
    channel: Messageable | None = bot.get_channel(channel_id)
    if not channel:
        logger.warning(f"Channel not found with ID: {channel_id}")
        return None

    message: str | None = make_message()
    if not message:
        logger.info("make_message() returned None, skipping message send.")
        return None

    title = DEFAULT_RIDE_TITLE
    color = DEFAULT_RIDE_COLOR

    message_lower = message.lower()

    for keyword, config in RIDE_TYPES_CONFIG.items():
        if keyword in message_lower:
            title = config["title"]
            color = config["color"]
            break

    embed = discord.Embed(
        title=title,
        description=message,
        color=color,
    )

    try:
        return await channel.send(
            allowed_mentions=discord.AllowedMentions(roles=True),
            embed=embed,
        )
    except discord.HTTPException as e:
        logger.error(f"Failed to send message to channel {channel_id}: {e}")
        return None


@feature_flag_enabled(FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB)
async def run_ask_rides_wed(bot: Bot) -> None:
    """Runner for Wednesday rides message."""
    await _ask_rides_template(bot, _make_wednesday_msg)


@feature_flag_enabled(FeatureFlagNames.ASK_FRIDAY_RIDES_JOB)
async def run_ask_rides_fri(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Runner for Friday rides message."""
    sent_message = await _ask_rides_template(bot, _make_friday_msg, channel_id)
    await sent_message.add_reaction("🪨")


@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_RIDES_JOB)
async def run_ask_rides_sun(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Runner for Sunday service rides message."""
    sent_message = await _ask_rides_template(bot, _make_sunday_msg, channel_id)
    reactions = ["🍔", "🏠", "✳️"]
    for emoji in reactions:
        await sent_message.add_reaction(emoji)

@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_CLASS_RIDES_JOB)
async def run_ask_rides_sun_class(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Runner for Sunday class rides message."""
    sent_message = await _ask_rides_template(bot, _make_sunday_msg_class, channel_id)
    await sent_message.add_reaction("📖")


async def run_ask_rides_header(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    channel: Messageable | None = bot.get_channel(channel_id)
    if not channel:
        logger.info("Error channel not found")
        return

    if (
        await feature_flag_status(FeatureFlagNames.ASK_SUNDAY_RIDES_JOB)
        or await feature_flag_status(FeatureFlagNames.ASK_FRIDAY_RIDES_JOB)
        or await feature_flag_status(FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB)
    ):
        await channel.send(
            _format_message("for this week!"),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
