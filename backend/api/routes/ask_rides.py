"""Ask Rides API Routes."""

import asyncio
import json
import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import require_admin, require_ride_coordinator
from api.constants import ASK_RIDES_DEFAULT_COUNT, ASK_RIDES_DEFAULT_OFFSET, SSE_HEARTBEAT_INTERVAL
from api.dependencies import require_bot, require_ready_bot
from bot.core import messages_broadcaster
from bot.core.database import AsyncSessionLocal
from bot.core.enums import (
    AskRidesMessage,
    AskRidesMessageType,
    CacheNamespace,
    DaysOfWeek,
    DaysOfWeekNumber,
    EmbedColorChoice,
    FeatureFlagNames,
    JobName,
)
from bot.jobs.ask_rides import get_ask_rides_status, run_ask_rides_all
from bot.repositories.global_settings_repository import GlobalSettingsRepository
from bot.services.ask_rides_messages_service import AskRidesMessagesService
from bot.services.feature_flags_service import FeatureFlagsService
from bot.services.locations_service import LocationsService
from bot.services.message_schedule_service import MessageScheduleService
from bot.services.non_discord_rides_service import NonDiscordRidesService
from bot.utils.ask_rides_defaults import ALLOWED_PLACEHOLDERS, DEFAULT_TEMPLATES
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


@router.post(
    "/send-now",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Manually Trigger Ask Rides",
    description="Manually trigger all ask rides messages immediately.",
)
async def send_now():
    """
    Manually trigger all ask rides messages immediately.

    This calls the same run_ask_rides_all function used by the scheduler,
    useful when the scheduled send was missed (e.g. due to a service crash).
    """
    bot = require_ready_bot()

    try:
        await run_ask_rides_all(bot)
        return {"success": True, "message": "Ask rides messages sent successfully"}
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


FELLOWSHIP_SEASON_KEY = "fellowship_season"


@router.get(
    "/fellowship-season",
    summary="Get Fellowship Season",
    description="Returns the active fellowship season from global settings.",
)
async def get_fellowship_season() -> dict:
    """Return 'friday' or 'wednesday' from global settings (default 'friday')."""
    async with AsyncSessionLocal() as session:
        season = await GlobalSettingsRepository.get(session, FELLOWSHIP_SEASON_KEY)
    return {"season": season or "friday"}


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
    svc = FeatureFlagsService()

    if request.season == "friday":
        enable_flag = FeatureFlagNames.ASK_FRIDAY_RIDES_JOB
        disable_flag = FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB
    else:
        enable_flag = FeatureFlagNames.ASK_WEDNESDAY_RIDES_JOB
        disable_flag = FeatureFlagNames.ASK_FRIDAY_RIDES_JOB

    try:
        async with AsyncSessionLocal() as session:
            await GlobalSettingsRepository.set(session, FELLOWSHIP_SEASON_KEY, request.season)
            await svc.modify_feature_flag(enable_flag.value, True, session)
            await svc.modify_feature_flag(disable_flag.value, False, session)
        await FeatureFlagsService.reinitialize_cache()
        await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
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


# ============================================================================
# Editable ask-rides message templates
# ============================================================================


def _serialize_template(message_type: AskRidesMessageType, template) -> dict:
    """Serialize an EffectiveTemplate plus its default, for one message type."""
    default = DEFAULT_TEMPLATES[message_type]
    return {
        "title": template.title,
        "body": template.body,
        "color": template.color,
        "is_customized": template.is_customized,
        "default": {
            "title": default.title,
            "body": default.body,
            "color": default.color.value,
        },
    }


@router.get(
    "/messages",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Get Ask Rides Message Templates",
    description="Get the effective (customized or default) title/body/color for all four "
    "ask-rides message types.",
)
async def get_message_templates() -> dict:
    """Return all four effective templates plus allowed colors/placeholders."""
    effective = await AskRidesMessagesService.get_effective_templates()
    return {
        "templates": {
            message_type.value: _serialize_template(message_type, template)
            for message_type, template in effective.items()
        },
        "allowed_colors": [c.value for c in EmbedColorChoice],
        "allowed_placeholders": {
            message_type.value: sorted(tokens)
            for message_type, tokens in ALLOWED_PLACEHOLDERS.items()
        },
    }


class UpdateMessageTemplateRequest(BaseModel):
    """Request body for updating an ask-rides message template."""

    title: str = Field(description="Embed title")
    body: str = Field(description="Embed body/description template")
    color: str = Field(description="Preset color key (see allowed_colors)")


@router.put(
    "/messages/{message_type}",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Update Ask Rides Message Template",
    description="Save a customized title/body/color for one ask-rides message type.",
)
async def update_message_template(
    message_type: str, body: UpdateMessageTemplateRequest, request: Request
) -> dict:
    """Validate and persist a customized template, then broadcast an SSE update."""
    try:
        msg_type = AskRidesMessageType(message_type)
    except ValueError as e:
        valid_types = [t.value for t in AskRidesMessageType]
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(valid_types)}",
        ) from e

    user = getattr(request.state, "user", None) or {}
    updated_by = user.get("email", "")

    try:
        updated = await AskRidesMessagesService.update_template(
            msg_type, body.title, body.body, body.color, updated_by
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    return _serialize_template(msg_type, updated)


@router.delete(
    "/messages/{message_type}",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Reset Ask Rides Message Template",
    description="Reset a customized ask-rides message template back to its default.",
)
async def reset_message_template(message_type: str) -> dict:
    """Delete the saved customization for a message type, reverting to the default."""
    try:
        msg_type = AskRidesMessageType(message_type)
    except ValueError as e:
        valid_types = [t.value for t in AskRidesMessageType]
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(valid_types)}",
        ) from e

    await AskRidesMessagesService.reset_template(msg_type)
    default = await AskRidesMessagesService.get_effective_template(msg_type)
    return _serialize_template(msg_type, default)


@router.get(
    "/messages/stream",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Stream Ask Rides Message Template Updates",
    description="SSE stream of live ask-rides message template edits.",
)
async def message_templates_stream() -> StreamingResponse:
    """SSE stream — emits a `templates_updated` event whenever a template is saved or reset."""

    async def event_generator():
        q = messages_broadcaster.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=SSE_HEARTBEAT_INTERVAL)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.debug("message_templates_stream: client disconnected")
        finally:
            messages_broadcaster.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
