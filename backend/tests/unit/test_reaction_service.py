"""Verify compatibility selectors read durable data without accessing Discord."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from ridebot.services import ride_events_service as events
from ridebot.services.reaction_service import ReactionService
from shared.core.enums import AskRidesMessage, RideOption
from tests.unit.test_ride_events import choice, record, register


@pytest.fixture(name="store")
def _store(ride_event_store):
    return ride_event_store


@pytest.fixture(autouse=True)
def cycle(monkeypatch):
    monkeypatch.setattr(
        events, "get_current_cycle_start", lambda: datetime(2026, 10, 19, tzinfo=UTC)
    )


@pytest.mark.asyncio
async def test_stored_choices_are_available_without_bot(store):
    await register()
    await record()
    bot = Mock()
    bot.get_channel.side_effect = AssertionError("Reads must not access Discord")
    service = ReactionService(bot)
    assert await service.get_usernames_who_reacted(789, 456) == {"alice"}
    bot.get_channel.assert_not_called()
    assert await service.get_usernames_who_reacted(999, 456) == set()


@pytest.mark.asyncio
async def test_return_filters_and_removals_use_saved_state(store):
    await register()
    await record(selection=choice("1", "alice", "🍔"))
    await record(selection=choice("2", "bob", "🏠"))
    service = ReactionService()
    assert await service.get_usernames_who_reacted(789, 456, RideOption.SUNDAY_DROPOFF_BACK) == {
        "bob"
    }
    assert await service.get_usernames_who_reacted(789, 456, RideOption.SUNDAY_DROPOFF_LUNCH) == {
        "alice"
    }
    await record(active=False)
    assert await service.get_usernames_who_reacted(789, 456) == {"bob"}


@pytest.mark.asyncio
async def test_current_message_is_scoped_to_channel_and_explicit_event_type(store):
    await register()
    service = ReactionService()
    assert await service.find_correct_message(AskRidesMessage.SUNDAY_SERVICE, 789) == 456
    assert await service.find_correct_message(AskRidesMessage.SUNDAY_SERVICE, 999) is None
    assert await service.find_correct_message(AskRidesMessage.SUNDAY_CLASS, 789) is None
    assert (await service._find_all_messages(789))[AskRidesMessage.SUNDAY_SERVICE] == 456


@pytest.mark.asyncio
async def test_driver_sources_are_separate_from_riders(store):
    ride = await register()
    await events.RideEventsService.bind_announcement(
        event_id=ride.id, channel_id="999", message_id="9999", signup_emojis=["👍"], kind="driver"
    )
    await record(message_id="9999", selection=choice("2", "driver", "👍"))
    assert (
        await events.RideEventsService.current_message(
            AskRidesMessage.SUNDAY_SERVICE, 999, kind="driver"
        )
        == 9999
    )
    assert (
        await events.RideEventsService.current_message(AskRidesMessage.SUNDAY_SERVICE, 999) is None
    )
    assert (
        await events.RideEventsService.breakdown(AskRidesMessage.SUNDAY_SERVICE, 999, kind="driver")
    )["reactions"] == {"👍": ["driver"]}
    assert (await events.RideEventsService.get_event(ride.id))[2] == []


@pytest.mark.asyncio
async def test_driver_reactions_reject_invalid_kind():
    with pytest.raises(ValueError, match="Invalid event"):
        await ReactionService().get_driver_reactions(AskRidesMessage.SUNDAY_CLASS)
