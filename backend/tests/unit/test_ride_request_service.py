"""Unit tests for ridebot/services/ride_request_service.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from ridebot.services import ride_request_service
from ridebot.services.ride_request_service import RideRequestService
from ridebot.utils.constants import (
    NEW_RIDER_CHANNEL_MEMORY_SECONDS,
    PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,
)
from ridebot.views.pickup_info import PickupInfoView
from shared.core.enums import CategoryIds


@pytest.fixture(autouse=True)
def _reset_rider_state():
    """Riders' locks and remembered channels are module-level; isolate each test."""
    ride_request_service._rider_locks.clear()
    ride_request_service._recently_created_channels.clear()
    yield
    ride_request_service._rider_locks.clear()
    ride_request_service._recently_created_channels.clear()


def _make_guild_and_category(existing_channel=None):
    category = MagicMock(spec=discord.CategoryChannel)
    category.id = int(CategoryIds.NEW_RIDES)
    category.channels = [existing_channel] if existing_channel else []

    guild = MagicMock(spec=discord.Guild)
    guild.categories = [category]
    guild.roles = []
    guild.default_role = MagicMock()
    guild.get_role.return_value = None
    return guild, category


def _make_user(name="alice", user_id=42):
    user = MagicMock(spec=discord.Member)
    user.id = user_id
    user.name = name
    user.mention = f"<@{name}>"
    return user


def _make_new_channel():
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "alice"
    channel.mention = "#alice"
    channel.send = AsyncMock()
    return channel


def _async_iter(items):
    """Build a fresh async iterator, mimicking `channel.history(...)`."""

    async def _gen(*args, **kwargs):
        for item in items:
            yield item

    return _gen


def _make_message(author_id=1, custom_ids=()):
    """A channel message, optionally carrying button components."""
    message = MagicMock()
    message.author.id = author_id
    message.components = [
        MagicMock(children=[MagicMock(custom_id=custom_id) for custom_id in custom_ids])
    ]
    return message


def _make_existing_channel(name="alice", history=()):
    """A channel already sitting in the new-rides category for this rider."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = name
    channel.mention = f"#{name}"
    sent_message = MagicMock()
    sent_message.pin = AsyncMock()
    channel.send = AsyncMock(return_value=sent_message)
    channel.history = _async_iter(history)
    return channel


def _make_bot(user_id=1):
    bot = MagicMock()
    bot.user.id = user_id
    return bot


@pytest.mark.asyncio
async def test_welcome_message_attaches_view():
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = AsyncMock()
    new_channel = _make_new_channel()
    guild.create_text_channel.return_value = new_channel

    bot = MagicMock()
    bot.get_channel.return_value = None
    service = RideRequestService(bot)

    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    new_channel.send.assert_awaited_once()
    _, kwargs = new_channel.send.call_args
    assert isinstance(kwargs["view"], PickupInfoView)


@pytest.mark.asyncio
async def test_existing_channel_is_reused_and_prompt_reposted():
    existing = _make_existing_channel()
    guild, _ = _make_guild_and_category(existing_channel=existing)
    guild.create_text_channel = AsyncMock()

    service = RideRequestService(MagicMock())
    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    guild.create_text_channel.assert_not_called()
    existing.send.assert_awaited_once()
    _, kwargs = existing.send.call_args
    assert isinstance(kwargs["view"], PickupInfoView)


@pytest.mark.asyncio
async def test_skips_repost_when_prompt_is_already_the_latest_message():
    """Reacting repeatedly must not stack identical prompts."""
    prompt = _make_message(author_id=1, custom_ids=(PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,))
    existing = _make_existing_channel(history=[prompt])
    guild, _ = _make_guild_and_category(existing_channel=existing)
    guild.create_text_channel = AsyncMock()

    service = RideRequestService(_make_bot(user_id=1))
    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is False
    existing.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_reposts_when_rider_replied_after_the_prompt():
    """A rider message on top means the prompt is buried, so prompt again."""
    rider_message = _make_message(author_id=999)
    existing = _make_existing_channel(history=[rider_message])
    guild, _ = _make_guild_and_category(existing_channel=existing)
    guild.create_text_channel = AsyncMock()

    service = RideRequestService(_make_bot(user_id=1))
    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    existing.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_reposts_when_history_cannot_be_read():
    """Fails open — prompting matters more than perfect de-duplication."""
    existing = _make_existing_channel()
    existing.history = MagicMock(side_effect=discord.Forbidden(MagicMock(status=403), "no perms"))
    guild, _ = _make_guild_and_category(existing_channel=existing)
    guild.create_text_channel = AsyncMock()

    service = RideRequestService(_make_bot())
    result = await service.handle_new_rider_reaction(_make_user(), guild)

    assert result is True
    existing.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_coordinator_announcement_on_channel_creation():
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = AsyncMock()
    new_channel = _make_new_channel()
    guild.create_text_channel.return_value = new_channel
    sent_message = MagicMock()
    sent_message.pin = AsyncMock()
    new_channel.send.return_value = sent_message

    bot = MagicMock()
    service = RideRequestService(bot)

    await service.handle_new_rider_reaction(_make_user(), guild)

    # The "new hooman!" notice is gone; coordinators hear about riders when they register.
    bot.get_channel.assert_not_called()


def _slow_create(channel):
    """A create_text_channel that yields to the event loop before returning."""

    async def _create(*args, **kwargs):
        for _ in range(5):
            await asyncio.sleep(0)
        return channel

    return AsyncMock(side_effect=_create)


@pytest.mark.asyncio
async def test_concurrent_reactions_create_only_one_channel():
    """Two reactions at once must not each create a channel for the same rider.

    The guild cache never learns about the new channel here, mimicking the gap
    before Discord's CHANNEL_CREATE event arrives.
    """
    prompt = _make_message(author_id=1, custom_ids=(PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,))
    new_channel = _make_existing_channel(history=[prompt])
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = _slow_create(new_channel)

    service = RideRequestService(_make_bot(user_id=1))
    user = _make_user()
    results = await asyncio.gather(
        service.handle_new_rider_reaction(user, guild),
        RideRequestService(_make_bot(user_id=1)).handle_new_rider_reaction(user, guild),
    )

    assert sorted(results) == [False, True]
    guild.create_text_channel.assert_awaited_once()
    new_channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_different_riders_are_not_serialized_together():
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = _slow_create(_make_new_channel())

    service = RideRequestService(_make_bot())
    await asyncio.gather(
        service.handle_new_rider_reaction(_make_user("alice", user_id=1), guild),
        service.handle_new_rider_reaction(_make_user("bob", user_id=2), guild),
    )

    assert guild.create_text_channel.await_count == 2


@pytest.mark.asyncio
async def test_remembered_channel_expires(monkeypatch):
    """After the memory window, a missing channel (e.g. deleted) is created again."""
    now = 1000.0
    monkeypatch.setattr(ride_request_service.time, "monotonic", lambda: now)
    guild, _ = _make_guild_and_category()
    guild.create_text_channel = AsyncMock(return_value=_make_new_channel())

    service = RideRequestService(_make_bot())
    user = _make_user()
    await service.handle_new_rider_reaction(user, guild)

    now += NEW_RIDER_CHANNEL_MEMORY_SECONDS + 1
    await service.handle_new_rider_reaction(user, guild)

    assert guild.create_text_channel.await_count == 2
