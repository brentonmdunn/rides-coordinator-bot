"""Ask Rides API Routes."""

import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_admin, require_ride_coordinator
from api.constants import ASK_RIDES_DEFAULT_COUNT, ASK_RIDES_DEFAULT_OFFSET
from api.dependencies import require_bot, require_ready_bot
from bot.core.enums import (
    AskRidesMessage,
    CacheNamespace,
    DaysOfWeek,
    DaysOfWeekNumber,
    FellowshipSeason,
    JobName,
)
from bot.jobs.ask_rides import get_ask_rides_status, run_ask_rides_manual
from bot.services.fellowship_season_service import FellowshipSeasonService
from bot.services.locations_service import LocationsService
from bot.services.message_schedule_service import MessageScheduleService
from bot.services.non_discord_rides_service import NonDiscordRidesService
from bot.utils.cache import invalidate_namespace
from bot.utils.time_helpers import get_next_date_obj, get_send_wednesday

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


class PauseRequest(BaseModel):
    """Request body for setting a pause."""

    is_paused: bool = Field(description="Whether to pause the job")
    resume_after_date: date | None = Field(
        default=None, description="Optional date after which the job should automatically resume"
    )


class SendNowRequest(BaseModel):
    """Request body for manually triggering ask rides messages."""

    scope: Literal["fellowship", "sunday", "both"] = Field(
        default="both",
        description=(
            "Which messages to send: 'fellowship' (Wed or Fri, whichever season is active), "
            "'sunday' (Sunday service + class), or 'both'."
        ),
    )


@router.post(
    "/send-now",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Manually Trigger Ask Rides",
    description="Manually trigger ask rides messages immediately for the requested scope.",
)
async def send_now(request: SendNowRequest | None = None):
    """
    Manually trigger ask rides messages immediately.

    This calls the same job runners used by the scheduler, useful when the
    scheduled send was missed (e.g. due to a service crash).
    """
    bot = require_ready_bot()
    scope = request.scope if request else "both"

    try:
        await run_ask_rides_manual(bot, scope)
        return {
            "success": True,
            "message": f"Ask rides messages sent successfully ({scope})",
        }
    except Exception as e:
        logger.exception("Error sending ask rides messages manually")
        raise HTTPException(status_code=500, detail=f"Failed to send messages: {e!s}") from e


@router.get(
    "/status",
    summary="Get Ask Rides Status",
    description="Get the status of all automated ask rides jobs.",
)
async def get_status():
    """
    Get status for all ask rides jobs.

    Returns:
        Dictionary with status for friday, sunday, and sunday_class jobs
    """
    bot = require_bot()

    status = await get_ask_rides_status(bot)
    return status


@router.get(
    "/pauses",
    summary="Get Pause Statuses",
    description="Get the pause status configurations for all ask rides jobs.",
)
async def get_pauses():
    """Get pause status for all ask rides jobs."""
    pauses = await MessageScheduleService.get_all_pauses()
    result = {}
    for pause in pauses:
        send_date = None
        if pause.resume_after_date:
            send_date = get_send_wednesday(pause.resume_after_date).isoformat()
        result[pause.job_name] = {
            "is_paused": pause.is_paused,
            "resume_after_date": pause.resume_after_date.isoformat()
            if pause.resume_after_date
            else None,
            "resume_send_date": send_date,
        }
    return result


@router.put(
    "/pauses/{job_name}",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Set Pause Status",
    description="Set or release the pause state for a specific job.",
)
async def set_pause(job_name: str, request: PauseRequest):
    """
    Set the pause state for a specific job.

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
        await MessageScheduleService.clear_pause(job_name)
        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
        logger.info(f"⏸️ Cleared pause for '{job_name}'")
        return {"success": True, "message": f"Resumed {job_name}"}

    # Setting a pause
    updated = await MessageScheduleService.set_pause(
        job_name, request.is_paused, request.resume_after_date
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")

    send_date = None
    if updated.resume_after_date:
        send_date = get_send_wednesday(updated.resume_after_date).isoformat()

    msg = f"Paused {job_name}"
    if updated.resume_after_date:
        msg += f" until {updated.resume_after_date.isoformat()} (send resumes {send_date})"
    else:
        msg += " indefinitely"

    logger.info(f"⏸️ {msg}")
    await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
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


@router.get(
    "/upcoming-dates/{job_name}",
    summary="Get Upcoming Dates",
    description="Get the mathematically projected upcoming event dates for a given job type.",
)
async def get_upcoming_dates(
    job_name: str, count: int = ASK_RIDES_DEFAULT_COUNT, offset: int = ASK_RIDES_DEFAULT_OFFSET
):
    """
    Get upcoming event dates for a job type.

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

    if job_name == JobName.WEDNESDAY:
        target_day = DaysOfWeek.WEDNESDAY
    elif job_name == JobName.FRIDAY:
        target_day = DaysOfWeek.FRIDAY
    else:
        target_day = DaysOfWeek.SUNDAY

    dates = []

    next_date = get_next_date_obj(target_day) + timedelta(weeks=offset)

    if job_name == JobName.WEDNESDAY and offset == 0:
        # For Wednesday fellowship the send day is the Monday 2 days before.
        # If that Monday has already passed, skip forward a week so we never
        # show a date whose send window is in the past.
        today = date.today()
        send_monday = next_date - timedelta(days=2)
        if send_monday < today:
            next_date += timedelta(weeks=1)

    for _ in range(count):
        if job_name == JobName.WEDNESDAY:
            # Send day is the Monday 2 days before the Wednesday event
            send_date = next_date - timedelta(
                days=(next_date.weekday() - DaysOfWeekNumber.MONDAY) % 7
            )
        else:
            send_date = get_send_wednesday(next_date)
        dates.append(
            {
                "event_date": next_date.isoformat(),
                "send_date": send_date.isoformat(),
                "label": next_date.strftime("%a %b %-d"),
            }
        )
        next_date += timedelta(weeks=1)

    return {"dates": dates, "has_more": True}


@router.get(
    "/fellowship-season",
    summary="Get Fellowship Season",
    description="Returns the active fellowship season from global settings.",
)
async def get_fellowship_season() -> dict:
    """Return 'friday' or 'wednesday' from global settings (default 'friday')."""
    season = await FellowshipSeasonService.get_season()
    return {"season": season.value}


class SetSeasonRequest(BaseModel):
    """Request body for setting the fellowship season."""

    season: Literal["friday", "wednesday"]


@router.post(
    "/fellowship-season",
    dependencies=[Depends(require_admin)],
    summary="Set Fellowship Season",
    description="Switches between Friday and Wednesday fellowship, persisting the choice globally.",
)
async def set_fellowship_season(request: SetSeasonRequest) -> dict:
    """Persist season to global settings and sync feature flags."""
    try:
        await FellowshipSeasonService.set_season(FellowshipSeason(request.season))
    except Exception as e:
        logger.exception("Error setting fellowship season")
        raise HTTPException(status_code=500, detail=f"Failed to set season: {e!s}") from e

    return {"season": request.season}


@router.get(
    "/reactions/{message_type}",
    summary="Get Reaction Breakdown",
    description="Get a detailed breakdown of user reactions on the target ask rides message.",
)
async def get_ask_rides_reactions(message_type: str):
    """
    Get detailed reaction breakdown for ask-rides messages.

    Args:
        message_type: One of "friday", "sunday", or "sunday_class"

    Returns:
        Dictionary with reactions mapping emojis to lists of usernames,
        username_to_name mapping, and message_found flag
    """
    bot = require_bot()

    # Map message_type to AskRidesMessage enum
    type_to_event: dict[str, AskRidesMessage] = {
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

    # Non-Discord riders are tracked per ride day; map the message type to a day.
    type_to_day: dict[str, str] = {
        JobName.FRIDAY: DaysOfWeek.FRIDAY,
        JobName.SUNDAY: DaysOfWeek.SUNDAY,
        JobName.SUNDAY_CLASS: DaysOfWeek.SUNDAY,
    }

    try:
        # Collect non-Discord riders for the day, grouped by their emoji tag.
        non_discord: dict[str, list[str]] = {}
        day = type_to_day.get(message_type.lower())
        if day is not None:
            rides = await NonDiscordRidesService().list_pickups(day)
            for ride in rides:
                if ride.emoji:
                    non_discord.setdefault(ride.emoji, []).append(ride.name)

        locations_svc = LocationsService(bot)
        result = await locations_svc.get_ask_rides_reactions(event)

        if not result:
            return {
                "message_type": message_type,
                "reactions": {},
                "username_to_name": {},
                "non_discord": non_discord,
                "message_found": False,
            }

        return {
            "message_type": message_type,
            **result,
            "non_discord": non_discord,
            "message_found": True,
        }

    except Exception as e:
        logger.exception(f"Error fetching ask-rides reactions for {message_type}")
        raise HTTPException(status_code=500, detail=str(e)) from e
