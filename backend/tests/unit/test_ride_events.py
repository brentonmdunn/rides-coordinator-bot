"""Exercise current signup identity and reconciliation against a real SQLite store."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from ridebot.services.ride_events_service import ReactionChoice, RideEventsService
from shared.core.enums import AskRidesMessageType
from shared.core.models import RideAnnouncement, RideEvent

OBSERVED = datetime(2026, 10, 21, 19, tzinfo=UTC)


@pytest.fixture(name="store")
def _store(ride_event_store):
    return ride_event_store


async def register(message_id="456", *, guild="123", event_date=date(2026, 10, 25)):
    ride = await RideEventsService.ensure_event(
        guild_id=guild,
        message_type=AskRidesMessageType.SUNDAY_SERVICE,
        event_date=event_date,
    )
    await RideEventsService.bind_announcement(
        event_id=ride.id,
        channel_id="789",
        message_id=message_id,
        signup_emojis=["🍔", "🏠"],
    )
    return ride


def choice(user_id="1", username="alice", emoji="🍔"):
    return ReactionChoice(user_id, username, "Discord Name", emoji)


async def record(*, selection=None, active=True, observed_at=OBSERVED, message_id="456"):
    return await RideEventsService.record_reaction(
        message_id=message_id,
        choice=selection or choice(),
        active=active,
        observed_at=observed_at,
    )


@pytest.mark.asyncio
async def test_event_identity_is_idempotent_and_scoped_to_guild_and_date(store):
    first = await register()
    assert (await register()).id == first.id
    assert (await register("457")).id == first.id
    assert (await register("458", guild="124")).id != first.id
    assert (await register("459", event_date=date(2026, 11, 1))).id != first.id
    async with store() as session:
        assert await session.scalar(select(func.count()).select_from(RideEvent)) == 3


@pytest.mark.asyncio
async def test_announcement_cannot_be_rebound_and_transaction_rolls_back(store):
    first = await register()
    second = await RideEventsService.ensure_event(
        guild_id="123", message_type=AskRidesMessageType.SUNDAY_CLASS, event_date=first.event_date
    )
    with pytest.raises(ValueError, match="already bound"):
        await RideEventsService.bind_announcement(
            event_id=second.id, channel_id="789", message_id="456", signup_emojis=["🍔", "🏠"]
        )
    async with store() as session:
        assert (await session.get(RideAnnouncement, "456")).event_id == first.id
