"""Verify import dry-runs and incomplete Discord snapshots cannot alter saved state."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from ridebot.services.ride_events_service import RideEventsService
from scripts import reconcile_ride_event


async def users(*, fail=False):
    yield SimpleNamespace(id=1, name="alice", display_name="Alice", bot=False)
    yield SimpleNamespace(id=2, name="bot", display_name="Bot", bot=True)
    if fail:
        raise RuntimeError("Incomplete Discord response")


@pytest.fixture
def importer(monkeypatch):
    monkeypatch.setenv("RIDEBOT_TOKEN", "test-token")
    message = SimpleNamespace(
        id=456,
        author=SimpleNamespace(id=99),
        reactions=[SimpleNamespace(emoji="🍔", users=lambda: users())],
    )
    channel = Mock(spec=discord.TextChannel)
    channel.id = 789
    channel.guild = SimpleNamespace(id=123)
    channel.fetch_message = AsyncMock(return_value=message)
    client = AsyncMock()
    client.user = SimpleNamespace(id=99)
    client.fetch_channel.return_value = channel
    client.__aenter__.return_value = client
    monkeypatch.setattr(reconcile_ride_event.discord, "Client", Mock(return_value=client))
    ensure = AsyncMock(return_value=SimpleNamespace(id=10))
    bind = AsyncMock()
    apply = AsyncMock()
    monkeypatch.setattr(RideEventsService, "ensure_event", ensure)
    monkeypatch.setattr(RideEventsService, "bind_announcement", bind)
    monkeypatch.setattr(RideEventsService, "reconcile", apply)
    args = SimpleNamespace(
        channel_id=789,
        message_id=456,
        message_type="sunday_service",
        event_date=date(2026, 10, 25),
        emoji=["🍔", "🏠"],
        apply=False,
    )
    return args, message, ensure, bind, apply


@pytest.mark.asyncio
async def test_dry_run_never_writes(importer):
    args, _, ensure, bind, apply = importer
    await reconcile_ride_event.reconcile(args)
    ensure.assert_not_awaited()
    bind.assert_not_awaited()
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_import_uses_explicit_date_and_excludes_bots(importer):
    args, _, ensure, bind, apply = importer
    args.apply = True
    await reconcile_ride_event.reconcile(args)
    assert ensure.call_args.kwargs["event_date"] == date(2026, 10, 25)
    bind.assert_awaited_once_with(
        event_id=10, channel_id="789", message_id="456", signup_emojis=["🍔", "🏠"]
    )
    choices = apply.call_args.kwargs["choices"]
    assert [(choice.discord_user_id, choice.emoji) for choice in choices] == [("1", "🍔")]


@pytest.mark.asyncio
async def test_incomplete_snapshot_leaves_database_untouched(importer):
    args, message, ensure, bind, apply = importer
    args.apply = True
    message.reactions[0].users = lambda: users(fail=True)
    with pytest.raises(RuntimeError, match="Incomplete"):
        await reconcile_ride_event.reconcile(args)
    ensure.assert_not_awaited()
    bind.assert_not_awaited()
    apply.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_authors_cannot_be_imported(importer):
    args, message, ensure, _, apply = importer
    args.apply = True
    message.author.id = 100
    with pytest.raises(ValueError, match="authored by RideBot"):
        await reconcile_ride_event.reconcile(args)
    ensure.assert_not_awaited()
    apply.assert_not_awaited()
