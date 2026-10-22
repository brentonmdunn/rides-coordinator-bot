"""Exercise current signup identity and reconciliation against a real SQLite store."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import func, select

from api.auth import require_ride_coordinator
from api.routes.ride_events import router
from ridebot.cogs.reactions import Reactions
from ridebot.repositories.ride_events_repository import RideEventsRepository
from ridebot.services.ride_events_service import ReactionChoice, RideEventsService
from shared.core.enums import AskRidesMessageType
from shared.core.models import Locations, RideAnnouncement, RideEvent, RideSignup

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


@pytest.mark.asyncio
async def test_repeated_delivery_username_change_and_independent_choices(store):
    ride = await register()
    await record()
    await record()
    await record(selection=choice(username="renamed"), observed_at=OBSERVED + timedelta(seconds=1))
    await record(selection=choice(username="renamed", emoji="🏠"))
    await record(active=False, observed_at=OBSERVED + timedelta(seconds=2))
    _, _, rows = await RideEventsService.get_event(ride.id)
    assert [(row.discord_user_id, row.emoji) for row, _ in rows] == [("1", "🏠")]
    async with store() as session:
        assert await session.scalar(select(func.count()).select_from(RideSignup)) == 2
    await record(observed_at=OBSERVED + timedelta(seconds=3))
    assert len((await RideEventsService.get_event(ride.id))[2]) == 2


@pytest.mark.asyncio
async def test_unmapped_messages_and_unconfigured_emojis_do_not_create_signups(store):
    assert not await record()
    await register()
    assert not await record(selection=choice(emoji="❤️"))
    async with store() as session:
        assert await session.scalar(select(func.count()).select_from(RideSignup)) == 0


@pytest.mark.asyncio
async def test_snapshot_recovers_missed_changes_without_overwriting_newer_events(store):
    ride = await register()
    await record()
    await record(selection=choice("2"))
    snapshot_time = OBSERVED + timedelta(seconds=5)
    # Gateway changes arrive while the external snapshot is still being fetched.
    await record(active=False, observed_at=snapshot_time + timedelta(seconds=1))
    await record(selection=choice("3"), observed_at=snapshot_time + timedelta(seconds=1))
    await RideEventsService.reconcile(
        message_id="456", choices=[choice(), choice("4")], observed_at=snapshot_time
    )
    _, announcements, rows = await RideEventsService.get_event(ride.id)
    assert {row.discord_user_id for row, _ in rows} == {"3", "4"}
    assert announcements[0].last_reconciled_at == snapshot_time.replace(tzinfo=None)
    # An older complete snapshot must not regress the state or freshness.
    await RideEventsService.reconcile(message_id="456", choices=[], observed_at=OBSERVED)
    assert len((await RideEventsService.get_event(ride.id))[2]) == 2


@pytest.mark.asyncio
async def test_snapshot_failure_rolls_back_removals_and_freshness(store, monkeypatch):
    ride = await register()
    await record()
    monkeypatch.setattr(
        RideEventsRepository, "set_reaction", AsyncMock(side_effect=RuntimeError("write failed"))
    )
    with pytest.raises(RuntimeError):
        await RideEventsService.reconcile(
            message_id="456", choices=[choice("2")], observed_at=OBSERVED + timedelta(seconds=5)
        )
    _, announcements, rows = await RideEventsService.get_event(ride.id)
    assert [row.discord_user_id for row, _ in rows] == ["1"]
    assert announcements[0].last_reconciled_at is None


def api_app(*, forbidden=False):
    app = FastAPI()
    app.include_router(router)

    def auth():
        if forbidden:
            raise HTTPException(status_code=403)
        return "coordinator@example.com"

    app.dependency_overrides[require_ride_coordinator] = auth
    return app


@pytest.mark.asyncio
async def test_database_only_api_merges_choices_and_matches_roster_by_id(store):
    ride = await register()
    await register("457")
    async with store() as session, session.begin():
        session.add(
            Locations(
                id=10,
                name="Registered Name",
                discord_username="old",
                discord_user_id="1",
                location="ERC",
            )
        )
        session.add(
            Locations(id=11, name="Other Person", discord_username="alice", discord_user_id="99")
        )
    await record(selection=choice(username="renamed"))
    await record(selection=choice(emoji="🏠"), message_id="457")
    await record(selection=choice("2", "alice"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app()), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/ride-events/{ride.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["event_date"] == "2026-10-25"
        assert len(data["signups"]) == 2
        registered, unknown = data["signups"]
        assert registered["person_id"] == 10
        assert registered["location"] == "ERC"
        assert len(registered["choices"]) == 2
        assert registered["choices"][0]["observed_at"].endswith("+00:00")
        assert unknown["person_id"] is None  # No mutable username join.
        assert data["announcements"][0]["last_reconciled_at"] is None
        listed = await client.get("/api/ride-events?date_from=2026-10-25&date_to=2026-10-25")
        assert [item["id"] for item in listed.json()] == [ride.id]
        assert (await client.get("/api/ride-events/999")).status_code == 404
        assert (
            await client.get("/api/ride-events?date_from=2026-10-25&date_to=2026-10-01")
        ).status_code == 422
        assert (
            await client.get("/api/ride-events?date_from=2026-01-01&date_to=2026-12-31")
        ).status_code == 422


@pytest.mark.asyncio
async def test_event_api_requires_coordinator():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app(forbidden=True)), base_url="http://test"
    ) as client:
        assert (await client.get("/api/ride-events/1")).status_code == 403


@pytest.mark.asyncio
async def test_signup_survives_discord_message_fetch_failure(store):
    ride = await register()
    member = SimpleNamespace(id=1, name="alice", display_name="Alice", bot=False)
    guild = Mock()
    guild.get_member.return_value = member
    channel = Mock(spec=discord.TextChannel)
    bot = Mock()
    bot.get_guild.return_value = guild
    bot.get_channel.return_value = channel
    cog = Reactions(bot, Mock(), Mock())
    cog._resolve_message = AsyncMock(return_value=None)
    payload = SimpleNamespace(guild_id=123, channel_id=789, message_id=456, user_id=1, emoji="🍔")
    await cog._handle_reaction_add(payload)
    assert len((await RideEventsService.get_event(ride.id))[2]) == 1
    await cog._handle_reaction_remove(payload)
    assert (await RideEventsService.get_event(ride.id))[2] == []


@pytest.mark.asyncio
async def test_announcement_persists_actual_event_date_before_sending(store, monkeypatch):
    from ridebot.jobs import ask_rides

    monkeypatch.setattr(ask_rides, "get_next_date_obj", lambda _: date(2027, 1, 3))
    monkeypatch.setattr(ask_rides, "resolve_channel_id", lambda _: 789)
    build = AsyncMock(return_value=(discord.Embed(title="Custom wording"), ("🍔",), None))
    monkeypatch.setattr(ask_rides, "build_ask_rides_message", build)
    channel = Mock(spec=discord.TextChannel)
    channel.guild = SimpleNamespace(id=123)
    sent = SimpleNamespace(id=456, add_reaction=AsyncMock())

    async def send(**kwargs):
        async with store() as session:
            persisted = (await session.scalars(select(RideEvent))).one()
            assert persisted.event_date == date(2027, 1, 3)
            assert persisted.message_type == "sunday_service"
        return sent

    channel.send = AsyncMock(side_effect=send)
    bot = Mock()
    bot.get_channel.return_value = channel
    assert await ask_rides._ask_rides_template(bot, AskRidesMessageType.SUNDAY_SERVICE) is sent
    build.assert_awaited_once_with(AskRidesMessageType.SUNDAY_SERVICE, event_date=date(2027, 1, 3))
    async with store() as session:
        announcement = await session.get(RideAnnouncement, "456")
        assert announcement.channel_id == "789"
        assert announcement.signup_emojis == ["🍔"]


@pytest.mark.asyncio
async def test_registered_event_metadata_overrides_audit_text_and_send_date(store, monkeypatch):
    from ridebot.services import ride_reaction_log_service
    from shared.core.enums import ReactionAction
    from shared.core.models import RideReactionEvent

    await register()
    monkeypatch.setattr(ride_reaction_log_service, "AsyncSessionLocal", store)
    monkeypatch.setattr(
        ride_reaction_log_service, "get_message_and_embed_content", lambda _: "Custom title"
    )
    monkeypatch.setattr(ride_reaction_log_service.reaction_broadcaster, "publish", AsyncMock())
    await ride_reaction_log_service.RideReactionLogService.record_ask_rides_reaction(
        SimpleNamespace(id=1, name="alice", display_name="Alice"),
        SimpleNamespace(message_id=456, emoji="🍔"),
        SimpleNamespace(created_at=OBSERVED),
        ReactionAction.ADD,
    )
    async with store() as session:
        audit = (await session.scalars(select(RideReactionEvent))).one()
        assert audit.ride_date == date(2026, 10, 25)
        assert audit.ride_type == "sunday"
