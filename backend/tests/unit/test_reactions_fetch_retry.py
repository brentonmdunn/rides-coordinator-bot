"""Tests for transient-5xx retry and graceful degradation in the Reactions cog (item B)."""

from unittest.mock import AsyncMock, Mock

import discord
import pytest
import tenacity

import shared.utils.discord_retry as discord_retry
from ridebot.cogs.reactions import Reactions


def _server_error() -> discord.DiscordServerError:
    resp = Mock()
    resp.status = 503
    resp.reason = "Service Unavailable"
    return discord.DiscordServerError(resp, "upstream connect error")


def _not_found() -> discord.NotFound:
    resp = Mock()
    resp.status = 404
    resp.reason = "Not Found"
    return discord.NotFound(resp, "unknown message")


@pytest.fixture(autouse=True)
def _no_retry_wait(monkeypatch):
    """Keep retry waits at zero so the suite stays fast."""
    monkeypatch.setattr(discord_retry._call.retry, "wait", tenacity.wait_none())


def _make_cog() -> Reactions:
    cog = Reactions(Mock(), Mock(), Mock())
    cog.bot.cached_messages = []  # empty cache by default; override per test
    cog._late_rides_react = AsyncMock()
    cog._log_reactions = AsyncMock()
    cog._new_rides_helper = AsyncMock()
    cog._check_if_ask_message = AsyncMock()
    cog._record_ask_rides_reaction = AsyncMock()
    return cog


def _wire_bot(cog: Reactions, channel: Mock) -> Mock:
    guild = Mock()
    member = Mock()
    member.bot = False
    guild.get_member.return_value = member
    cog.bot.get_guild.return_value = guild
    cog.bot.get_channel.return_value = channel
    return guild


def _payload() -> Mock:
    payload = Mock(spec=discord.RawReactionActionEvent)
    payload.guild_id = 916817752918982716
    payload.channel_id = 939950319721406464
    payload.message_id = 1554930864163397674
    payload.user_id = 42
    payload.emoji = "🍔"
    return payload


# --- is_transient_discord_error predicate ---------------------------------


def test_predicate_retries_server_error():
    assert discord_retry.is_transient_discord_error(_server_error()) is True


def test_predicate_does_not_retry_not_found():
    assert discord_retry.is_transient_discord_error(_not_found()) is False


def test_predicate_retries_os_error():
    assert discord_retry.is_transient_discord_error(ConnectionResetError()) is True


# --- fetch_message_with_retry ---------------------------------------------


@pytest.mark.asyncio
async def test_fetch_retries_then_succeeds():
    message = Mock(spec=discord.Message)
    channel = Mock()
    channel.fetch_message = AsyncMock(side_effect=[_server_error(), message])

    got = await discord_retry.fetch_message_with_retry(channel, 1)

    assert got is message
    assert channel.fetch_message.await_count == 2


@pytest.mark.asyncio
async def test_fetch_not_found_fails_fast():
    channel = Mock()
    channel.fetch_message = AsyncMock(side_effect=_not_found())

    with pytest.raises(discord.NotFound):
        await discord_retry.fetch_message_with_retry(channel, 1)

    assert channel.fetch_message.await_count == 1


@pytest.mark.asyncio
async def test_fetch_exhausts_retries_then_raises():
    channel = Mock()
    channel.fetch_message = AsyncMock(side_effect=_server_error())

    with pytest.raises(discord.DiscordServerError):
        await discord_retry.fetch_message_with_retry(channel, 1)

    assert channel.fetch_message.await_count == 3


# --- _handle_reaction_add --------------------------------------------------


@pytest.mark.asyncio
async def test_add_retries_then_handles_normally(monkeypatch):
    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    message = Mock(spec=discord.Message)
    channel.fetch_message = AsyncMock(side_effect=[_server_error(), message])
    _wire_bot(cog, channel)

    await cog._handle_reaction_add(_payload())

    assert channel.fetch_message.await_count == 2
    cog._record_ask_rides_reaction.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_exhausted_degrades_without_crashing(monkeypatch):
    send_error = AsyncMock()
    monkeypatch.setattr("ridebot.cogs.reactions.send_error_to_discord", send_error)

    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(side_effect=_server_error())
    _wire_bot(cog, channel)

    # Must not raise.
    await cog._handle_reaction_add(_payload())

    send_error.assert_awaited_once()
    cog._record_ask_rides_reaction.assert_not_awaited()
    cog._late_rides_react.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_not_found_degrades_single_attempt(monkeypatch):
    send_error = AsyncMock()
    monkeypatch.setattr("ridebot.cogs.reactions.send_error_to_discord", send_error)

    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(side_effect=_not_found())
    _wire_bot(cog, channel)

    await cog._handle_reaction_add(_payload())

    assert channel.fetch_message.await_count == 1
    send_error.assert_awaited_once()
    cog._record_ask_rides_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_uses_cached_message_without_fetch():
    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock()
    _wire_bot(cog, channel)
    cached = Mock(spec=discord.Message)
    cached.id = 1554930864163397674
    cog.bot.cached_messages = [cached]

    await cog._handle_reaction_add(_payload())

    channel.fetch_message.assert_not_awaited()
    cog._record_ask_rides_reaction.assert_awaited_once()


# --- _handle_reaction_remove -----------------------------------------------


@pytest.mark.asyncio
async def test_remove_exhausted_degrades_without_crashing(monkeypatch):
    send_error = AsyncMock()
    monkeypatch.setattr("ridebot.cogs.reactions.send_error_to_discord", send_error)

    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(side_effect=_server_error())
    _wire_bot(cog, channel)

    await cog._handle_reaction_remove(_payload())

    send_error.assert_awaited_once()
    cog._record_ask_rides_reaction.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_uses_cached_message_without_fetch():
    cog = _make_cog()
    channel = Mock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock()
    _wire_bot(cog, channel)
    cached = Mock(spec=discord.Message)
    cached.id = 1554930864163397674
    cog.bot.cached_messages = [cached]

    await cog._handle_reaction_remove(_payload())

    channel.fetch_message.assert_not_awaited()
    cog._record_ask_rides_reaction.assert_awaited_once()
