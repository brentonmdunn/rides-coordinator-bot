"""
jobs/ask_rides.py

Scheduled jobs for asking for rides.
"""

import discord
from discord.ext import commands

from enums import ChannelIds, RoleIds, DaysOfWeekNumber

from utils.time_helpers import get_next_date
from utils.format_message import ping_role_with_message

WILDCARD_DATES: list[str] = ["5/16", "5/18", "5/23", "6/13"]
CLASS_DATES: list[str] = ["5/4", "5/11", "5/25", "6/1", "6/8", "6/15"]


def make_friday_msg() -> str | None:
    """Create message for Friday rides."""
    formatted_date = get_next_date(DaysOfWeekNumber.FRIDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return f"React if you need a ride for Friday night fellowship {formatted_date} (leave between 7 and 7:10pm)!"


def make_sunday_msg() -> str | None:
    """Create message for Sunday service rides."""
    formatted_date = get_next_date(DaysOfWeekNumber.SUNDAY)
    if formatted_date in WILDCARD_DATES:
        return None
    return f"React if you need a ride for Sunday {formatted_date} (leave between 10 and 10:10 am)!"


def make_sunday_msg_class() -> str | None:
    """Create message for Sunday class rides."""
    formatted_date = get_next_date(DaysOfWeekNumber.SUNDAY)
    if formatted_date in WILDCARD_DATES or formatted_date not in CLASS_DATES:
        return None
    return f"React if you need a ride to Bible Theology Class on Sunday {formatted_date} (leave between 8:30 and 8:40 am)"


def format_message(message: str) -> str:
    """Adds @Rides to message."""
    return ping_role_with_message(RoleIds.RIDES, message)


async def run_ask_rides_fri(bot):
    """Runner for Friday rides message."""
    channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
    if not channel:
        print("Error channel not found")
        return
    message: str = make_friday_msg()
    if message is None:
        return
    await channel.send(
        format_message(message),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )


async def run_ask_rides_sun(bot):
    """Runner for Sunday service rides message."""
    channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
    if not channel:
        print("Error channel not found")
        return
    message: str = make_sunday_msg()
    print(message)
    if message is None:
        return
    await channel.send(
        format_message(message),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )


async def run_ask_rides_sun_class(bot: commands.Bot) -> None:
    """Runner for Sunday class rides message."""
    channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
    if not isinstance(channel, discord.abc.Messageable):
        print("Error channel not found")
        return
    message: str = make_sunday_msg_class()
    if message is None:
        return
    await channel.send(
        format_message(message),
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
