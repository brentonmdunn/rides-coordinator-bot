"""Exercise recovery and persistence of existing ride signup behavior."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import discord
import pytest

from ridebot.services import ride_events_service as module
from ridebot.services.ride_events_service import RideEventsService
from shared.core.enums import AskRidesMessageType
from shared.core.models import Locations
from tests.unit.test_ride_events import OBSERVED, choice, record, register


@pytest.fixture(name="store")
def _store(ride_event_store):
    return ride_event_store


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
