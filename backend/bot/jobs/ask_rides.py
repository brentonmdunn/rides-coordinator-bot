"""jobs/ask_rides.py

Scheduled jobs for asking for rides.
"""

import os
from collections.abc import Callable

import discord
from discord.abc import Messageable
from discord.ext.commands import Bot

from bot.core.enums import (
    CacheNamespace,
    ChannelIds,
    DaysOfWeek,
    DaysOfWeekNumber,
    FeatureFlagNames,
    JobName,
    RoleIds,
)
from bot.core.logger import logger
from bot.repositories.calendar_repository import CalendarRepository
from bot.repositories.feature_flags_repository import FeatureFlagsRepository
from bot.repositories.message_schedule_repository import MessageScheduleRepository
from bot.utils.cache import alru_cache, warm_ask_rides_message_cache
from bot.utils.checks import feature_flag_enabled
from bot.utils.format_message import ping_role_with_message, ping_user
from bot.utils.time_helpers import get_next_date, get_next_date_obj

WILDCARD_DATES: list[str] = ["6/20", "6/27", "6/29"]
CLASS_DATES: list[str] = []


def _get_dynamic_ttl() -> int:
    """
    Calculate dynamic TTL based on current time.

    Returns shorter TTL during high-activity periods (Wednesday 11:59 AM - 3 PM)
    when messages are being sent and reactions are actively changing.

    Returns:
        60 seconds during Wednesday 11:59 AM - 3 PM, 180 seconds otherwise
    """
    from datetime import datetime

    now = datetime.now()

    # Wednesday is weekday 2 (0=Monday)
    if now.weekday() == 2 and 11 <= now.hour < 13:
        return 60  # Short TTL during active period

    return 60 * 60  # Longer TTL during quiet periods


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
    return (
        f"React to this message if you need a ride to Bible Theology Class on Sunday "
        f"{formatted_date} (leave between 8:30 and 8:40am). "
        "Make sure to also react to the message below for 🍔, 🏠, or ✳️."
    )


def _format_message(message: str) -> str:
    """Adds @Rides to message."""
    return ping_role_with_message(RoleIds.RIDES, message)


RIDE_TYPES_CONFIG = {
    JobName.FRIDAY: {
        "title": "Rides to Friday Fellowship",
        "color": discord.Color.from_rgb(227, 132, 212),  # Pink/Magenta
    },
    "class": {
        "title": "Rides to Bible Theology Class",
        "color": discord.Color.blurple(),
    },
    JobName.SUNDAY: {
        "title": "Rides to Sunday Service",
        "color": discord.Color.blue(),
    },
}

DEFAULT_RIDE_TITLE = "Rides Announcement"
DEFAULT_RIDE_COLOR = discord.Color.default()

# Emojis that the bot automatically adds to each message type
# This is the single source of truth for bot reactions (used by both
# job runners and API helpers to exclude bot reactions from user counts)
BOT_REACTIONS = {
    JobName.FRIDAY: ["🪨"],
    JobName.SUNDAY: ["🍔", "🏠", "✳️"],
    JobName.SUNDAY_CLASS: ["📖"],
}


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
        logger.error("make_message() returned None, skipping message send.")
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
    if await MessageScheduleRepository.is_job_paused(JobName.FRIDAY):
        logger.info("Blocking run_ask_rides_fri - job is paused")
        return
    sent_message = await _ask_rides_template(bot, _make_friday_msg, channel_id)
    for emoji in BOT_REACTIONS[JobName.FRIDAY]:
        await sent_message.add_reaction(emoji)


def _should_send_ask_rides_sun() -> bool:
    """Helper method to determine if we should send the Sunday rides message."""
    repo = CalendarRepository()
    gcal_event_summaries = repo.get_event_summaries(get_next_date_obj(DaysOfWeek.SUNDAY))
    return all("wildcard" not in event.lower() for event in gcal_event_summaries)


@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_RIDES_JOB)
async def run_ask_rides_sun(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Runner for Sunday service rides message."""
    if await MessageScheduleRepository.is_job_paused(JobName.SUNDAY):
        logger.info("Blocking run_ask_rides_sun - job is paused")
        return
    if not _should_send_ask_rides_sun():
        logger.info("Blocking run_ask_rides_sun due to wildcard detected on mastercalendar")
        channel: Messageable | None = bot.get_channel(
            ChannelIds.SERVING__DRIVER_BOT_SPAM,
        )
        if not channel:
            logger.info("Error channel not found")
            return
        await channel.send(
            "Widlcard detected on <https://www.lsccsd.com/calendar> so sunday rides were not sent."
        )
        return

    sent_message = await _ask_rides_template(bot, _make_sunday_msg, channel_id)
    for emoji in BOT_REACTIONS[JobName.SUNDAY]:
        await sent_message.add_reaction(emoji)


def _should_send_ask_rides_sun_class() -> bool:
    """Helper method to determine if we should send the Sunday class rides message."""
    repo = CalendarRepository()
    gcal_event_summaries = repo.get_event_summaries(get_next_date_obj(DaysOfWeek.SUNDAY))
    return any("sunday school" in event.lower() for event in gcal_event_summaries)


@feature_flag_enabled(FeatureFlagNames.ASK_SUNDAY_CLASS_RIDES_JOB)
async def run_ask_rides_sun_class(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Runner for Sunday class rides message."""
    if await MessageScheduleRepository.is_job_paused(JobName.SUNDAY_CLASS):
        logger.info("Blocking run_ask_rides_sun_class - job is paused")
        return
    if not _should_send_ask_rides_sun_class():
        logger.info("Blocking run_ask_rides_sun_class due to no class detected on mastercalendar")
        return
    sent_message = await _ask_rides_template(bot, _make_sunday_msg_class, channel_id)
    for emoji in BOT_REACTIONS[JobName.SUNDAY_CLASS]:
        await sent_message.add_reaction(emoji)


async def run_ask_rides_header(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Run the job to send the ask rides header."""

    channel: Messageable | None = bot.get_channel(channel_id)
    if not channel:
        logger.info("Error channel not found")
        return

    if (
        (
            await FeatureFlagsRepository.get_feature_flag_status(
                FeatureFlagNames.ASK_SUNDAY_RIDES_JOB
            )
            and _should_send_ask_rides_sun()
        )
        or (
            await FeatureFlagsRepository.get_feature_flag_status(
                FeatureFlagNames.ASK_SUNDAY_CLASS_RIDES_JOB
            )
            and _should_send_ask_rides_sun_class()
        )
        or await FeatureFlagsRepository.get_feature_flag_status(
            FeatureFlagNames.ASK_FRIDAY_RIDES_JOB
        )
        or await FeatureFlagsRepository.get_feature_flag_status(
            FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB
        )
    ):
        await channel.send(
            _format_message("for this week!"),
            allowed_mentions=discord.AllowedMentions(roles=True),
        )


async def run_ask_rides_all(
    bot: Bot, channel_id=ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
) -> None:
    """Run the job to send all ask rides messages."""

    await run_ask_rides_header(bot, channel_id)
    await run_ask_rides_fri(bot, channel_id)
    await run_ask_rides_sun_class(bot, channel_id)
    await run_ask_rides_sun(bot, channel_id)

    # Invalidate and warm caches since new messages were sent
    await warm_ask_rides_message_cache(bot, channel_id)


# State for rotating periodic warmers
_periodic_warmer_idx = 0


async def run_periodic_cache_warming(bot: Bot) -> None:
    """Rotates through the 2 reaction namespaces, warming one every time it runs."""
    global _periodic_warmer_idx
    from bot.core.enums import AskRidesMessage, CacheNamespace, ChannelIds
    from bot.services.locations_service import LocationsService
    from bot.utils.cache import invalidate_namespace

    locations_svc = LocationsService(bot)

    try:
        if _periodic_warmer_idx == 0:
            logger.info("Periodic cache warming: ASK_RIDES_REACTIONS")
            invalidate_namespace(CacheNamespace.ASK_RIDES_REACTIONS)
            await locations_svc.get_ask_rides_reactions(AskRidesMessage.SUNDAY_SERVICE)
            await locations_svc.get_ask_rides_reactions(AskRidesMessage.FRIDAY_FELLOWSHIP)

            s_msg_id = await locations_svc._find_correct_message(
                AskRidesMessage.SUNDAY_SERVICE, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
            )
            f_msg_id = await locations_svc._find_correct_message(
                AskRidesMessage.FRIDAY_FELLOWSHIP, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
            )
            if s_msg_id:
                await locations_svc._get_usernames_who_reacted(
                    ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS, s_msg_id
                )
            if f_msg_id:
                await locations_svc._get_usernames_who_reacted(
                    ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS, f_msg_id
                )
        elif _periodic_warmer_idx == 1:
            logger.info("Periodic cache warming: ASK_DRIVERS_REACTIONS")
            invalidate_namespace(CacheNamespace.ASK_DRIVERS_REACTIONS)
            await locations_svc.get_driver_reactions(AskRidesMessage.FRIDAY_FELLOWSHIP)
            await locations_svc.get_driver_reactions(AskRidesMessage.SUNDAY_SERVICE)
    except Exception as e:
        logger.error(f"Error checking cache {_periodic_warmer_idx}: {e}")

    _periodic_warmer_idx = (_periodic_warmer_idx + 1) % 2


# ============================================================================
# API Helper Functions (for dashboard status)
# ============================================================================


def get_next_run_time(job_name: str) -> str:
    """
    Calculate the next scheduled run time for a job.

    Args:
        job_name: A JobName value ("friday", "sunday", or "sunday_class")

    Returns:
        ISO format datetime string of next run time
    """
    from datetime import datetime, timedelta

    # All jobs currently run Wednesday at 12:00 PM (from job_scheduler.py)
    now = datetime.now()

    # Find next Wednesday
    days_until_wednesday = (2 - now.weekday()) % 7  # 2 = Wednesday (0=Monday)
    if days_until_wednesday == 0 and now.hour >= 12:
        # If it's Wednesday but past 12 PM, go to next Wednesday
        days_until_wednesday = 7

    next_run = now + timedelta(days=days_until_wednesday)
    next_run = next_run.replace(hour=12, minute=0, second=0, microsecond=0)

    return next_run.isoformat()


async def find_message_in_history(
    messages: list[discord.Message], job_type: str, current_week_start
) -> dict | None:
    """
    Find the most recent message for a job type in the provided messages list.
    """
    keywords = {
        JobName.FRIDAY: "friday",
        JobName.SUNDAY: "sunday service",
        JobName.SUNDAY_CLASS: "theology class",
    }

    keyword = keywords.get(job_type, "")
    bot_emojis = BOT_REACTIONS.get(job_type, [])

    for message in messages:
        # Check if message is from current week
        if message.created_at.replace(tzinfo=None) < current_week_start:
            continue

        if message.embeds and keyword.lower() in message.embeds[0].description.lower():
            # Found a matching message from current week
            reactions_dict = {}
            for reaction in message.reactions:
                count = reaction.count
                if str(reaction.emoji) in bot_emojis:
                    count -= 1
                reactions_dict[str(reaction.emoji)] = count

            return {"message_id": str(message.id), "reactions": reactions_dict}

    return None


@alru_cache(ttl=_get_dynamic_ttl, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_STATUS)
async def get_ask_rides_status(bot: Bot) -> dict:
    """
    Get status for all ask rides jobs.

    Args:
        bot: Discord bot instance

    Returns:
        Dictionary with status for friday, sunday, and sunday_class jobs
    """
    from datetime import datetime, timedelta

    now = datetime.now()

    # Sent status is active from Wednesday 12:00 PM to Sunday 11:59 PM
    is_sent_window = (now.weekday() == 2 and now.hour >= 12) or (3 <= now.weekday() <= 6)

    # Check feature flags
    friday_enabled = await FeatureFlagsRepository.get_feature_flag_status(
        FeatureFlagNames.ASK_FRIDAY_RIDES_JOB
    )
    sunday_enabled = await FeatureFlagsRepository.get_feature_flag_status(
        FeatureFlagNames.ASK_SUNDAY_RIDES_JOB
    )
    sunday_class_enabled = await FeatureFlagsRepository.get_feature_flag_status(
        FeatureFlagNames.ASK_SUNDAY_CLASS_RIDES_JOB
    )

    # Check pause statuses
    pause_statuses = await MessageScheduleRepository.get_all_pause_statuses()
    pause_map = {}
    for p in pause_statuses:
        send_date = None
        if p.resume_after_date:
            send_date = MessageScheduleRepository.get_send_wednesday(
                p.resume_after_date
            ).isoformat()
        pause_map[p.job_name] = {
            "is_paused": p.is_paused,
            "resume_after_date": p.resume_after_date.isoformat() if p.resume_after_date else None,
            "resume_send_date": send_date,
        }

    # Check conditions
    sunday_will_send = _should_send_ask_rides_sun() if sunday_enabled else False
    sunday_class_will_send = _should_send_ask_rides_sun_class() if sunday_class_enabled else False

    # Fetch last messages - OPTIMIZED: Fetch history once
    try:
        channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        if channel:
            # Calculate the start of current week (last Wednesday at noon when jobs run)
            days_since_wednesday = (now.weekday() - 2) % 7  # 2 = Wednesday
            if now.weekday() < 2:  # Monday or Tuesday
                days_since_wednesday += 7  # Go back to previous week's Wednesday

            current_week_start = now - timedelta(days=days_since_wednesday)
            current_week_start = current_week_start.replace(
                hour=12, minute=0, second=0, microsecond=0
            )

            # Fetch recent messages (last 20)
            messages = [msg async for msg in channel.history(limit=20)]

            friday_last_msg = await find_message_in_history(
                messages, JobName.FRIDAY, current_week_start
            )
            sunday_last_msg = await find_message_in_history(
                messages, JobName.SUNDAY, current_week_start
            )
            sunday_class_last_msg = await find_message_in_history(
                messages, JobName.SUNDAY_CLASS, current_week_start
            )
        else:
            friday_last_msg = None
            sunday_last_msg = None
            sunday_class_last_msg = None
    except Exception as e:
        logger.error(f"Error fetching messages history: {e}")
        friday_last_msg = None
        sunday_last_msg = None
        sunday_class_last_msg = None

    # Default pause info for jobs that may not have a row yet
    default_pause = {"is_paused": False, "resume_after_date": None, "resume_send_date": None}

    # Build status response
    status = {
        JobName.FRIDAY: {
            "enabled": friday_enabled,
            "will_send": friday_enabled,
            "sent_this_week": is_sent_window and friday_last_msg is not None,
            "reason": None if friday_enabled else "feature_flag_disabled",
            "next_run": get_next_run_time(JobName.FRIDAY),
            "last_message": friday_last_msg,
            "pause": pause_map.get(JobName.FRIDAY, default_pause),
        },
        JobName.SUNDAY: {
            "enabled": sunday_enabled,
            "will_send": sunday_will_send,
            "sent_this_week": is_sent_window and sunday_last_msg is not None,
            "reason": None
            if sunday_enabled and sunday_will_send
            else ("feature_flag_disabled" if not sunday_enabled else "wildcard_detected"),
            "next_run": get_next_run_time(JobName.SUNDAY),
            "last_message": sunday_last_msg,
            "pause": pause_map.get(JobName.SUNDAY, default_pause),
        },
        JobName.SUNDAY_CLASS: {
            "enabled": sunday_class_enabled,
            "will_send": sunday_class_will_send,
            "sent_this_week": is_sent_window and sunday_class_last_msg is not None,
            "reason": None
            if sunday_class_enabled and sunday_class_will_send
            else ("feature_flag_disabled" if not sunday_class_enabled else "no_class_scheduled"),
            "next_run": get_next_run_time(JobName.SUNDAY_CLASS),
            "last_message": sunday_class_last_msg,
            "pause": pause_map.get(JobName.SUNDAY_CLASS, default_pause),
        },
    }

    return status
