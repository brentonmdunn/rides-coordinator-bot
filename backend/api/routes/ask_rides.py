"""Ask Rides API Routes."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bot.api import get_bot
from bot.core.enums import AskRidesMessage, CacheNamespace, JobName
from bot.core.logger import logger
from bot.jobs.ask_rides import get_ask_rides_status, run_ask_rides_all
from bot.repositories.message_schedule_repository import MessageScheduleRepository
from bot.services.locations_service import LocationsService
from bot.utils.cache import invalidate_namespace

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
            "resume_after_date": pause.resume_after_date.isoformat()
            if pause.resume_after_date
            else None,
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
        invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
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
    invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
    return {
        "success": True,
        "message": msg,
        "pause": {
            "is_paused": updated.is_paused,
            "resume_after_date": updated.resume_after_date.isoformat()
            if updated.resume_after_date
            else None,
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
    target_weekday = 4 if job_name == JobName.FRIDAY else 6

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
        dates.append(
            {
                "event_date": next_date.isoformat(),
                "send_date": send_wednesday.isoformat(),
                "label": next_date.strftime("%a %b %-d"),
            }
        )
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

    # Map message_type to AskRidesMessage enum
    type_to_event = {
        JobName.FRIDAY: AskRidesMessage.FRIDAY_FELLOWSHIP,
        JobName.SUNDAY: AskRidesMessage.SUNDAY_SERVICE,
        JobName.SUNDAY_CLASS: AskRidesMessage.SUNDAY_CLASS,
    }

    event = type_to_event.get(message_type.lower())
    if not event:
        valid_types = [j.value for j in JobName]
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(valid_types)}",
        )

    try:
        locations_svc = LocationsService(bot)
        result = await locations_svc.get_ask_rides_reactions(event)

        if not result:
            return {
                "message_type": message_type,
                "reactions": {},
                "username_to_name": {},
                "message_found": False,
            }

        return {
            "message_type": message_type,
            **result,
            "message_found": True,
        }

    except Exception as e:
        logger.error(f"Error fetching ask-rides reactions for {message_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
