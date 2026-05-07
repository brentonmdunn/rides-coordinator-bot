"""
Reaction Log API Endpoint

GET /api/reaction-log — returns ride reaction events grouped by message.
"""

import datetime
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from bot.core.database import AsyncSessionLocal
from bot.repositories.ride_reaction_events_repository import RideReactionEventsRepository

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
    date_str = (
        ride_date.strftime("%-m/%-d/%Y") if hasattr(ride_date, "strftime") else str(ride_date)
    )
    # Use a nicer format: "May 2, 2026"
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
        async with AsyncSessionLocal() as session:
            events = await RideReactionEventsRepository.get_events(
                session,
                ride_type=ride_type,
                date_from=date_from,
                date_to=date_to,
                emoji=emoji,
            )

        # Group by message_id while preserving insertion order for events
        groups: dict[str, dict] = defaultdict(
            lambda: {"ride_type": None, "ride_date": None, "events": []}
        )
        for event in events:
            mid = event.message_id
            groups[mid]["ride_type"] = event.ride_type
            groups[mid]["ride_date"] = event.ride_date
            groups[mid]["events"].append(
                ReactionEventOut(
                    id=event.id,
                    discord_username=event.discord_username,
                    display_name=event.display_name,
                    emoji=event.emoji,
                    action=event.action,
                    occurred_at=event.occurred_at,
                )
            )

        # Sort: newest rides first (ride_date desc, then message_id desc as tiebreaker)
        def _sort_key(item: tuple) -> tuple:
            mid, data = item
            rd = data["ride_date"]
            # None dates sort to the end
            date_key = rd if rd is not None else datetime.date.min
            return (date_key, mid)

        sorted_groups = sorted(groups.items(), key=_sort_key, reverse=True)

        rides = [
            RideGroup(
                message_id=mid,
                ride_type=data["ride_type"],
                ride_date=data["ride_date"],
                label=_format_label(data["ride_type"], data["ride_date"]),
                events=data["events"],
            )
            for mid, data in sorted_groups
        ]

        return ReactionLogResponse(rides=rides)

    except Exception:
        logger.exception("Failed to fetch reaction log")
        raise HTTPException(status_code=500, detail="Failed to fetch reaction log") from None
