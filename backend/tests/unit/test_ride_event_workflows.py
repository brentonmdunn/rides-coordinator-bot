"""Exercise recovery, canonical requests, and confirmed capacity/assignment invariants."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import httpx
import pytest

from ridebot.services import ride_events_service as module
from ridebot.services.ride_event_sync_service import RideEventSyncService, legacy_event_date
from ridebot.services.ride_events_service import RideEventsService
from shared.core.enums import AskRidesMessageType
from shared.core.models import Locations
from tests.unit.test_ride_events import OBSERVED, api_app, choice, record, register


@pytest.fixture(name="store")
def _store(ride_event_store):
    return ride_event_store


@pytest.mark.asyncio
async def test_clear_fences_snapshot_and_deleted_source_cannot_resurrect(store):
    ride = await register()
    await record()
    cleared_at = OBSERVED + timedelta(seconds=5)
    await RideEventsService.clear_reactions(message_id="456", observed_at=cleared_at)
    await RideEventsService.reconcile(message_id="456", choices=[choice("2")], observed_at=OBSERVED)
    assert (await RideEventsService.workflow(ride.id))[1] == []
    await record(observed_at=cleared_at + timedelta(seconds=1))
    await RideEventsService.clear_reactions(
        message_id="456", observed_at=cleared_at + timedelta(seconds=2), deleted=True
    )
    await RideEventsService.reconcile(
        message_id="456", choices=[choice()], observed_at=cleared_at + timedelta(seconds=3)
    )
    assert (await RideEventsService.workflow(ride.id))[1] == []
    detail = await RideEventsService.get_event(ride.id)
    assert detail[0].id == ride.id
    assert detail[1][0].deleted_at is not None
    assert (await RideEventsService.workflow(ride.id))[-1]["is_stale"]


@pytest.mark.asyncio
async def test_complete_empty_snapshot_rejects_delayed_unknown_add(store):
    await register()
    await RideEventsService.reconcile(
        message_id="456", choices=[], observed_at=OBSERVED + timedelta(seconds=5)
    )
    assert not await record(selection=choice("new"), observed_at=OBSERVED)


@pytest.mark.asyncio
async def test_cleared_emoji_preserves_other_choice(store):
    ride = await register()
    await record()
    await record(selection=choice(emoji="🏠"))
    await RideEventsService.clear_reactions(
        message_id="456", emoji="🍔", observed_at=OBSERVED + timedelta(seconds=1)
    )
    assert [row.emoji for row, _ in (await RideEventsService.get_event(ride.id))[2]] == ["🏠"]


@pytest.mark.asyncio
async def test_custom_request_survives_reaction_removal_and_manual_rider_needs_no_discord(store):
    ride = await register()
    await record()
    await RideEventsService.save_custom_request(
        message_id="456", discord_user_id="1", name="Alice", text="Return early"
    )
    await record(active=False, observed_at=OBSERVED + timedelta(seconds=1))
    manual = await RideEventsService.save_request(
        event_id=ride.id, name="Guest", location="ERC", return_preference="home"
    )
    requests = (await RideEventsService.workflow(ride.id))[1]
    assert {r.name for r in requests} == {"Alice", "Guest"}
    assert next(r for r in requests if r.discord_user_id).details == "Return early"
    assert manual.discord_user_id is None
    assert manual.identity_key.startswith("manual:")


@pytest.mark.asyncio
async def test_pickups_join_ids_and_exclude_class_only_on_outbound_leg(store):
    service = await register()
    await record(selection=choice("1", "renamed"))
    await record(selection=choice("2", "another"))
    async with store() as session, session.begin():
        session.add_all(
            [
                Locations(
                    name="Alice", discord_user_id="1", discord_username="old", location="ERC"
                ),
                Locations(
                    name="Bob", discord_user_id="2", discord_username="another", location="Revelle"
                ),
            ]
        )
    school = await RideEventsService.ensure_event(
        guild_id="123", message_type=AskRidesMessageType.SUNDAY_CLASS, event_date=service.event_date
    )
    await RideEventsService.bind_announcement(
        event_id=school.id, channel_id="789", message_id="457", signup_emojis=["📖"]
    )
    await record(message_id="457", selection=choice("1", "renamed", "📖"))
    locations, reacted, found, _, _ = await RideEventsService.pickup_data(event_id=service.id)
    assert locations == {"Revelle": [("Bob", "another")]}
    assert reacted == found == {"another"}
    from shared.core.enums import RideOption

    returning = await RideEventsService.pickup_data(
        event_id=service.id, option=RideOption.SUNDAY_DROPOFF_LUNCH
    )
    assert {name for people in returning[0].values() for name, _ in people} == {"Alice", "Bob"}


@pytest.mark.asyncio
async def test_assignment_replacement_is_atomic_and_per_leg_capacity_is_enforced(store):
    ride = await register()
    first = await RideEventsService.save_request(
        event_id=ride.id, name="One", return_preference="home"
    )
    second = await RideEventsService.save_request(
        event_id=ride.id, name="Two", return_preference="home"
    )
    offer = await RideEventsService.save_offer(
        event_id=ride.id,
        discord_user_id="99",
        discord_username="driver",
        capacity=1,
        directions=["pickup", "return"],
    )
    pickup = {"request_id": first.id, "driver_offer_id": offer.id, "direction": "pickup"}
    returning = {"request_id": second.id, "driver_offer_id": offer.id, "direction": "return"}
    await RideEventsService.save_assignments(ride.id, [pickup, returning])
    with pytest.raises(ValueError, match="capacity"):
        await RideEventsService.save_assignments(
            ride.id, [pickup, {**pickup, "request_id": second.id}]
        )
    assert len((await RideEventsService.workflow(ride.id))[4]) == 2
    with pytest.raises(ValueError, match="once per leg"):
        await RideEventsService.save_assignments(ride.id, [pickup, pickup])
    with pytest.raises(ValueError, match="this event"):
        await RideEventsService.save_assignments(ride.id, [{**pickup, "request_id": 9999}])
    with pytest.raises(ValueError, match="capacity"):
        await RideEventsService.save_offer(
            event_id=ride.id,
            discord_user_id="99",
            discord_username="driver",
            capacity=None,
            directions=["pickup", "return"],
        )
    assert (await RideEventsService.workflow(ride.id))[3][0].capacity == 1
    with pytest.raises(ValueError, match="return preference"):
        await RideEventsService.save_offer(
            event_id=ride.id,
            discord_user_id="99",
            discord_username="driver",
            capacity=1,
            directions=["pickup", "return"],
            return_preference="lunch",
        )
    assert (await RideEventsService.workflow(ride.id))[3][0].return_preference == "either"
    await RideEventsService.save_request(
        event_id=ride.id, identity_key=first.identity_key, name="One", active=False
    )
    assert len((await RideEventsService.workflow(ride.id))[4]) == 1


@pytest.mark.asyncio
async def test_withdrawn_driver_retires_confirmed_assignments(store):
    ride = await register()
    await record()
    await RideEventsService.bind_announcement(
        event_id=ride.id,
        channel_id="789",
        message_id="driver",
        signup_emojis=["👍", "❌"],
        kind="driver",
    )
    await record(message_id="driver", selection=choice("99", "driver", "👍"))
    offer = await RideEventsService.save_offer(
        event_id=ride.id,
        discord_user_id="99",
        discord_username="driver",
        capacity=4,
        directions=["pickup"],
    )
    request = (await RideEventsService.workflow(ride.id))[1][0]
    await RideEventsService.save_assignments(
        ride.id, [{"request_id": request.id, "driver_offer_id": offer.id, "direction": "pickup"}]
    )
    await record(
        message_id="driver",
        selection=choice("99", "driver", "❌"),
        observed_at=OBSERVED + timedelta(seconds=1),
    )
    workflow = await RideEventsService.workflow(ride.id)
    assert workflow[3][0].availability == "unavailable"
    assert workflow[4] == []


@pytest.mark.asyncio
async def test_failed_snapshot_retains_choices_and_exposes_error(store):
    ride = await register()
    await record()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(side_effect=OSError("offline"))
    bot = Mock()
    bot.get_channel.return_value = channel
    announcement = (await RideEventsService.get_event(ride.id))[1][0]
    assert not await RideEventSyncService(bot).reconcile_announcement(announcement)
    workflow = await RideEventsService.workflow(ride.id)
    assert len(workflow[1]) == 1
    assert workflow[-1]["is_stale"]
    assert workflow[-1]["errors"]


@pytest.mark.asyncio
async def test_snapshot_filters_bots_and_incomplete_iterator_never_clears(store):
    ride = await register()
    await record()

    async def users():
        yield SimpleNamespace(id=2, name="human", display_name="Human", bot=False)
        yield SimpleNamespace(id=3, name="bot", display_name="Bot", bot=True)

    channel = Mock(spec=discord.TextChannel)
    reaction = SimpleNamespace(emoji="🍔", users=users)
    channel.fetch_message = AsyncMock(return_value=SimpleNamespace(reactions=[reaction]))
    bot = Mock()
    bot.get_channel.return_value = channel
    announcement = (await RideEventsService.get_event(ride.id))[1][0]
    adapter = RideEventSyncService(bot)
    assert await adapter.reconcile_announcement(announcement)
    assert [r.discord_user_id for r in (await RideEventsService.workflow(ride.id))[1]] == ["2"]

    async def broken():
        yield SimpleNamespace(id=4, name="partial", display_name="Partial", bot=False)
        raise OSError("Incomplete response")

    reaction.users = broken
    assert not await adapter.reconcile_announcement(announcement)
    assert [r.discord_user_id for r in (await RideEventsService.workflow(ride.id))[1]] == ["2"]


def test_legacy_dates_are_explicit_unambiguous_and_year_safe():
    created = datetime(2026, 12, 30, 19, tzinfo=UTC)
    assert legacy_event_date("Sunday 1/3", created, 6) == date(2027, 1, 3)
    assert legacy_event_date("Sunday rides", created, 6) is None
    assert legacy_event_date("1/3 or 1/10", created, 6) is None
    assert legacy_event_date("2/30", created, 6) is None


@pytest.mark.asyncio
async def test_coordinator_api_can_save_and_read_requests_offline(store):
    ride = await register()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api_app()), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/ride-events/{ride.id}/requests", json={"name": "Guest", "location": "ERC"}
        )
        assert response.status_code == 200
        request_id = response.json()["id"]
        offer = await client.put(
            f"/api/ride-events/{ride.id}/driver-offers/99",
            json={"discord_username": "driver", "capacity": 4, "directions": ["pickup"]},
        )
        assert offer.status_code == 200
        plan = [
            {"request_id": request_id, "driver_offer_id": offer.json()["id"], "direction": "pickup"}
        ]
        assert (
            await client.put(f"/api/ride-events/{ride.id}/assignments", json={"assignments": plan})
        ).status_code == 200
        detail = (await client.get(f"/api/ride-events/{ride.id}")).json()
        assert detail["assignments"] == plan
        assert detail["requests"][0]["name"] == "Guest"
        assert (
            await client.put(
                f"/api/ride-events/{ride.id}/assignments", json={"assignments": plan + plan}
            )
        ).status_code == 422


@pytest.mark.asyncio
async def test_missing_member_cache_still_persists_add_and_remove(store):
    from ridebot.cogs.reactions import Reactions

    ride = await register()
    bot = Mock()
    guild = Mock()
    guild.get_member.return_value = None
    bot.get_guild.return_value = guild
    bot.get_channel.return_value = Mock(spec=discord.TextChannel)
    cog = Reactions(bot, Mock(), Mock())
    payload = SimpleNamespace(guild_id=123, channel_id=789, message_id=456, user_id=1, emoji="🍔")
    await cog._handle_reaction_add(payload)
    assert (await RideEventsService.workflow(ride.id))[1][0].discord_user_id == "1"
    await cog._handle_reaction_remove(payload)
    assert (await RideEventsService.workflow(ride.id))[1] == []


@pytest.mark.asyncio
async def test_reconnect_failure_is_retried_and_overlapping_triggers_are_coalesced():
    import asyncio

    from ridebot.cogs.ride_event_sync import RideEventSync

    bot = Mock()
    bot.is_ready.return_value = True
    cog = RideEventSync(bot)
    cog.reconcile.is_running = Mock(return_value=True)
    cog.service = Mock()
    cog.service.run = AsyncMock(return_value=False)
    await cog.run_sync()
    assert cog.needs_discovery
    started, release = asyncio.Event(), asyncio.Event()

    async def run(**kwargs):
        started.set()
        await release.wait()
        return True

    cog.service.run = AsyncMock(side_effect=run)
    first = asyncio.create_task(cog.on_ready())
    await started.wait()
    await cog.on_resumed()
    release.set()
    await first
    assert cog.service.run.await_count == 1
    assert not cog.needs_discovery


@pytest.mark.asyncio
async def test_sync_cog_does_not_start_tasks_before_discord_client_initialization():
    from discord.ext import commands

    from ridebot.cogs.ride_event_sync import RideEventSync

    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())
    cog = RideEventSync(bot)
    await cog.cog_load()
    assert not cog.reconcile.is_running()
    cog.cog_unload()
    await bot.close()


@pytest.mark.asyncio
async def test_legacy_non_discord_interface_updates_canonical_requests_atomically(
    store, monkeypatch
):
    from ridebot.repositories.non_discord_rides_repository import NonDiscordRidesRepository
    from shared.core.models import NonDiscordRides

    monkeypatch.setattr(
        module, "get_current_cycle_start", lambda: datetime(2026, 10, 19, tzinfo=UTC)
    )
    async with store() as session:
        legacy = await NonDiscordRidesRepository.create_ride(
            session,
            NonDiscordRides(name="Guest", date=date(2026, 10, 25), location="ERC", emoji="🍔"),
        )
    event = await RideEventsService.resolve_event(day="sunday")
    assert event is not None  # No Discord projection is required for a manual request.
    requests = (await RideEventsService.workflow(event.id))[1]
    assert [(r.name, r.return_preference) for r in requests] == [("Guest", "lunch")]
    async with store() as session:
        row = await NonDiscordRidesRepository.get_ride(session, legacy.name, legacy.date)
        await NonDiscordRidesRepository.delete_ride(session, row)
    assert (await RideEventsService.workflow(event.id))[1] == []
