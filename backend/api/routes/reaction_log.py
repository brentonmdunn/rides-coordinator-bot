"""
Reaction Log API Endpoint

GET /api/reaction-log — returns ride reaction events grouped by message.
"""

import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from bot.services.ride_reaction_log_service import RideReactionLogService

logger = logging.getLogger(__name__)

router = APIRouter()


class ReactionEventOut(BaseModel):
    """A single reaction or un-reaction event."""

    id: int
    discord_username: str
    display_name: str | None
    emoji: str
    action: str
    occurred_at: datetime.datetime


class RideGroup(BaseModel):
    """A group of reaction events for a single ride announcement message."""

    message_id: str
    ride_type: str | None
    ride_date: datetime.date | None
    label: str
    events: list[ReactionEventOut]


class ReactionLogResponse(BaseModel):
    """Response model for the reaction log endpoint."""

    rides: list[RideGroup]


def _format_label(ride_type: str | None, ride_date: datetime.date | None) -> str:
    """
    Build a human-readable label such as "Friday · May 2, 2026".

    Args:
        ride_type: One of "friday", "sunday", "sunday_class", "wednesday", or None.
        ride_date: The date of the ride, or None.

    Returns:
        A formatted label string.
    """
    type_label = ride_type.replace("_", " ").title() if ride_type else "Unknown"
    if ride_date is None:
        return type_label
    date_str = ride_date.strftime("%B %-d, %Y")
    return f"{type_label} · {date_str}"


@router.get(
    "/api/reaction-log",
    response_model=ReactionLogResponse,
    dependencies=[Depends(require_ride_coordinator)],
)
async def get_reaction_log(
    ride_type: str | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
    emoji: str | None = None,
):
    """
    Return ride reaction events grouped by message, newest rides first.

    Query params (all optional):
        ride_type: friday | sunday | sunday_class | wednesday
        date_from: ISO date — include events on or after this ride_date
        date_to: ISO date — include events on or before this ride_date
        emoji: filter to a specific emoji string
    """
    try:
        sorted_groups = await RideReactionLogService.get_grouped_events(
            ride_type=ride_type,
            date_from=date_from,
            date_to=date_to,
            emoji=emoji,
        )

        rides = [
            RideGroup(
                message_id=mid,
                ride_type=data["ride_type"],
                ride_date=data["ride_date"],
                label=_format_label(data["ride_type"], data["ride_date"]),
                events=[
                    ReactionEventOut(
                        id=event.id,
                        discord_username=event.discord_username,
                        display_name=event.display_name,
                        emoji=event.emoji,
                        action=event.action,
                        occurred_at=event.occurred_at,
                    )
                    for event in data["events"]
                ],
            )
            for mid, data in sorted_groups
        ]

        return ReactionLogResponse(rides=rides)

    except Exception:
        logger.exception("Failed to fetch reaction log")
        raise HTTPException(status_code=500, detail="Failed to fetch reaction log") from None
