"""Read recorded ride events/signups without requiring a live Discord bot."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from api.auth import require_ride_coordinator
from ridebot.services.ride_events_service import RideEventsService
from shared.core.enums import AskRidesMessageType
from shared.utils.datetimes import to_iso_utc

router = APIRouter(
    prefix="/api/ride-events",
    tags=["ride-events"],
    dependencies=[Depends(require_ride_coordinator)],
)


class RideEventOut(BaseModel):
    """An explicit event identity and the actual date of the ride."""

    id: int
    guild_id: str
    message_type: AskRidesMessageType
    event_date: date


class AnnouncementOut(BaseModel):
    """Source message and freshness of its last complete reconciliation."""

    message_id: str
    channel_id: str
    signup_emojis: list[str]
    last_reconciled_at: str | None
    kind: str = "rider"
    deleted_at: str | None = None
    sync_error: str | None = None


class ChoiceOut(BaseModel):
    """An active choice whose interpretation belongs to its announcement template."""

    message_id: str
    emoji: str
    observed_at: str


class SignupOut(BaseModel):
    """One rider per event, with all currently recorded reaction choices."""

    discord_user_id: str
    discord_username: str
    display_name: str
    person_id: int | None
    name: str | None
    location: str | None
    choices: list[ChoiceOut]


class RideEventDetailOut(RideEventOut):
    """Recorded event state; freshness does not imply Discord is currently reachable."""

    announcements: list[AnnouncementOut]
    signups: list[SignupOut]
    freshness: dict = Field(default_factory=dict)


@router.get("", response_model=list[RideEventOut])
async def list_events(
    date_from: date,
    date_to: date,
    guild_id: str | None = Query(default=None, pattern=r"^[0-9]+$"),
):
    """List dated events within a range of at most 93 days."""
    if not 0 <= (date_to - date_from).days <= 93:
        raise HTTPException(status_code=422, detail="Date range must span 0 to 93 days")
    events = await RideEventsService.list_events(
        date_from=date_from, date_to=date_to, guild_id=guild_id
    )
    return [
        RideEventOut(
            id=event.id,
            guild_id=event.guild_id,
            message_type=AskRidesMessageType(event.message_type),
            event_date=event.event_date,
        )
        for event in events
    ]


@router.get("/{event_id}", response_model=RideEventDetailOut)
async def get_event(event_id: int = Path(gt=0)):
    """Return saved signups, including riders who have not registered pickup info."""
    result = await RideEventsService.get_event(event_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Ride event not found")
    event, announcements, rows = result
    workflow = await RideEventsService.workflow(event.id)
    assert workflow is not None
    _, _, _, state = workflow
    riders: dict[str, SignupOut] = {}
    latest_observation = {}
    for choice, person in rows:
        rider = riders.setdefault(
            choice.discord_user_id,
            SignupOut(
                discord_user_id=choice.discord_user_id,
                discord_username=choice.discord_username,
                display_name=choice.display_name,
                person_id=person.id if person else None,
                name=person.name if person else None,
                location=person.location if person else None,
                choices=[],
            ),
        )
        if choice.updated_at >= latest_observation.get(choice.discord_user_id, choice.updated_at):
            rider.discord_username = choice.discord_username
            rider.display_name = choice.display_name
            latest_observation[choice.discord_user_id] = choice.updated_at
        observed_at = to_iso_utc(choice.updated_at)
        assert observed_at is not None
        rider.choices.append(
            ChoiceOut(
                message_id=choice.message_id,
                emoji=choice.emoji,
                observed_at=observed_at,
            )
        )
    return RideEventDetailOut(
        id=event.id,
        guild_id=event.guild_id,
        message_type=AskRidesMessageType(event.message_type),
        event_date=event.event_date,
        announcements=[
            AnnouncementOut(
                message_id=item.message_id,
                channel_id=item.channel_id,
                signup_emojis=item.signup_emojis,
                last_reconciled_at=to_iso_utc(item.last_reconciled_at),
                kind=item.kind,
                deleted_at=to_iso_utc(item.deleted_at),
                sync_error=item.sync_error,
            )
            for item in announcements
        ],
        signups=list(riders.values()),
        freshness=state,
    )


@router.get("/current/{day}", response_model=RideEventDetailOut)
async def current_event(day: str):
    """Resolve legacy day tabs to an explicit event ID."""
    try:
        event = await RideEventsService.resolve_event(day=day)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Ride event not found")
    return await get_event(event.id)


@router.post("/{event_id}/reconcile", response_model=RideEventDetailOut)
async def reconcile_event(event_id: int):
    """Refresh only this event's saved sources without sending Discord messages."""
    from api.dependencies import require_ready_bot
    from ridebot.services.ride_event_sync_service import RideEventSyncService

    detail = await RideEventsService.get_event(event_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Ride event not found")
    adapter = RideEventSyncService(require_ready_bot())
    for announcement in detail[1]:
        if announcement.deleted_at is None:
            await adapter.reconcile_announcement(announcement)
    return await get_event(event_id)
