"""Exercise recovery and persistence of existing ride signup behavior."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import discord
import pytest

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
