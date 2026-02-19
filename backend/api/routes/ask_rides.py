"""Ask Rides API Routes."""

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.api import get_bot
from bot.core.database import AsyncSessionLocal
from bot.core.enums import ChannelIds, JobName
from bot.core.logger import logger
from bot.jobs.ask_rides import get_ask_rides_status, run_ask_rides_all
from bot.repositories.locations_repository import LocationsRepository
from bot.repositories.message_schedule_repository import MessageScheduleRepository

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


class PauseRequest(BaseModel):
    """Request body for setting a pause."""

    is_paused: bool
    resume_after_date: date | None = None


@router.post("/send-now")
async def send_now():
    """
    Manually trigger all ask rides messages immediately.

    This calls the same run_ask_rides_all function used by the scheduler,
    useful when the scheduled send was missed (e.g. due to a service crash).
    """
    bot = get_bot()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot not initialized or not ready")

    try:
        await run_ask_rides_all(bot)
        return {"success": True, "message": "Ask rides messages sent successfully"}
    except Exception as e:
        logger.error(f"Error sending ask rides messages manually: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send messages: {e!s}") from e


@router.get("/status")
async def get_status():
    """
    Get status for all ask rides jobs.

    Returns:
        Dictionary with status for friday, sunday, and sunday_class jobs
    """
    bot = get_bot()
    if not bot:
        return {"error": "Bot not initialized"}

    status = await get_ask_rides_status(bot)
    return status


@router.get("/pauses")
async def get_pauses():
    """Get pause status for all ask rides jobs."""
    pauses = await MessageScheduleRepository.get_all_pause_statuses()
    result = {}
    for pause in pauses:
        send_date = None
        if pause.resume_after_date:
            send_date = MessageScheduleRepository.get_send_wednesday(
                pause.resume_after_date
            ).isoformat()
        result[pause.job_name] = {
            "is_paused": pause.is_paused,
            "resume_after_date": pause.resume_after_date.isoformat() if pause.resume_after_date else None,
            "resume_send_date": send_date,
        }
    return result


@router.put("/pauses/{job_name}")
async def set_pause(job_name: str, request: PauseRequest):
    """Set the pause state for a specific job.

    Args:
        job_name: One of "friday", "sunday", "sunday_class".
        request: PauseRequest with is_paused and optional resume_after_date.
    """
    valid_jobs = tuple(j.value for j in JobName)
    if job_name not in valid_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"job_name must be one of: {', '.join(valid_jobs)}",
        )

    if not request.is_paused:
        # Resuming — clear the pause
        await MessageScheduleRepository.clear_pause(job_name)
        get_ask_rides_status.cache_clear()
        logger.info(f"⏸️ Cleared pause for '{job_name}'")
        return {"success": True, "message": f"Resumed {job_name}"}

    # Setting a pause
    updated = await MessageScheduleRepository.set_pause(
        job_name, request.is_paused, request.resume_after_date
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")

    send_date = None
    if updated.resume_after_date:
        send_date = MessageScheduleRepository.get_send_wednesday(
            updated.resume_after_date
        ).isoformat()

    msg = f"Paused {job_name}"
    if updated.resume_after_date:
        msg += f" until {updated.resume_after_date.isoformat()} (send resumes {send_date})"
    else:
        msg += " indefinitely"

    logger.info(f"⏸️ {msg}")
    get_ask_rides_status.cache_clear()
    return {
        "success": True,
        "message": msg,
        "pause": {
            "is_paused": updated.is_paused,
            "resume_after_date": updated.resume_after_date.isoformat() if updated.resume_after_date else None,
            "resume_send_date": send_date,
        },
    }


@router.get("/upcoming-dates/{job_name}")
async def get_upcoming_dates(job_name: str, count: int = 6, offset: int = 0):
    """Get upcoming event dates for a job type.

    Args:
        job_name: One of "friday", "sunday", "sunday_class".
        count: Number of dates to return (default 6).
        offset: Number of dates to skip (for pagination).
    """
    valid_jobs = tuple(j.value for j in JobName)
    if job_name not in valid_jobs:
        raise HTTPException(
            status_code=400,
            detail=f"job_name must be one of: {', '.join(valid_jobs)}",
        )

    # Determine which weekday to compute
    # Friday = weekday 4, Sunday = weekday 6
    if job_name == JobName.FRIDAY:
        target_weekday = 4  # Friday
    else:
        target_weekday = 6  # Sunday (both sunday and sunday_class)

    today = date.today()
    dates = []

    # Find the next occurrence
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # Skip today
    next_date = today + timedelta(days=days_ahead)

    # Skip 'offset' dates
    next_date += timedelta(weeks=offset)

    for _ in range(count):
        send_wednesday = MessageScheduleRepository.get_send_wednesday(next_date)
        dates.append({
            "event_date": next_date.isoformat(),
            "send_date": send_wednesday.isoformat(),
            "label": next_date.strftime("%a %b %-d"),
        })
        next_date += timedelta(weeks=1)

    return {"dates": dates, "has_more": True}


@router.get("/reactions/{message_type}")
async def get_ask_rides_reactions(message_type: str):
    """
    Get detailed reaction breakdown for ask-rides messages.

    Args:
        message_type: One of "friday", "sunday", or "sunday_class"

    Returns:
        Dictionary with reactions mapping emojis to lists of usernames,
        username_to_name mapping, and message_found flag
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Validate message_type
    valid_types = [j.value for j in JobName]
    if message_type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(valid_types)}",
        )

    try:
        channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        if not channel:
            logger.error(f"Channel {ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS} not found")
            raise HTTPException(status_code=500, detail="Channel not found")

        # Search keywords for each message type
        keywords = {
            JobName.FRIDAY: "friday",
            JobName.SUNDAY: "sunday service",
            JobName.SUNDAY_CLASS: "theology class",
        }

        keyword = keywords.get(message_type.lower(), "")

        # Find the most recent message for this type
        # Search in the last 20 messages (same as get_last_message_reactions)
        target_message = None
        async for message in channel.history(limit=20):
            if message.embeds and keyword.lower() in message.embeds[0].description.lower():
                target_message = message
                break

        if not target_message:
            return {
                "message_type": message_type,
                "reactions": {},
                "username_to_name": {},
                "message_found": False,
            }

        # Collect reactions by emoji, excluding bot reactions
        reactions_by_emoji = defaultdict(list)
        all_usernames = set()

        for reaction in target_message.reactions:
            # Only process reactions that aren't from the bot itself
            emoji_str = str(reaction.emoji)
            async for user in reaction.users():
                if not user.bot:
                    username = user.name
                    reactions_by_emoji[emoji_str].append(username)
                    all_usernames.add(username)

        # Get display names for all usernames
        locations_repo = LocationsRepository()
        async with AsyncSessionLocal() as session:
            username_to_name = await locations_repo.get_names_for_usernames(session, all_usernames)

        return {
            "message_type": message_type,
            "reactions": dict(reactions_by_emoji),
            "username_to_name": username_to_name,
            "message_found": True,
        }

    except Exception as e:
        logger.error(f"Error fetching ask-rides reactions for {message_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e

