"""Unit tests for stonesbot/cogs/event_thread_reactions.py."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from shared.core.enums import FeatureFlagNames
from shared.repositories.feature_flags_repository import FeatureFlagsRepository
from stonesbot.cogs.event_thread_reactions import EventThreadReactions


@pytest.fixture(autouse=True)
def _enable_event_threads():
    """Enable EVENT_THREADS via the cache so the decorator lets calls through."""
    FeatureFlagsRepository._cache[FeatureFlagNames.EVENT_THREADS] = True
    yield
    FeatureFlagsRepository._cache.pop(FeatureFlagNames.EVENT_THREADS, None)


def _make_payload(guild_id=1, channel_id=2, message_id=3, user_id=4):
    payload = MagicMock(spec=discord.RawReactionActionEvent)
    payload.guild_id = guild_id
    payload.channel_id = channel_id
    payload.message_id = message_id
    payload.user_id = user_id
    payload.emoji = "👍"
    return payload


def _make_member(user_id=4, is_bot=False, name="alice"):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.bot = is_bot
    member.name = name
    return member


def _make_cog(guild=None, channel=None, thread_service=None):
    bot = MagicMock()
    bot.get_guild.return_value = guild
    bot.get_channel.return_value = channel
    thread_service = thread_service or AsyncMock()
    cog = EventThreadReactions(bot, thread_service)
    return cog, bot, thread_service


# ---------------------------------------------------------------------------
# Guard: no guild_id (DM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_when_guild_id_missing():
    payload = _make_payload(guild_id=None)
    cog, _, thread_service = _make_cog()

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_when_guild_id_missing():
    payload = _make_payload(guild_id=None)
    cog, _, thread_service = _make_cog()

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Guard: guild not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_when_guild_missing():
    payload = _make_payload()
    cog, _, thread_service = _make_cog(guild=None)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_when_guild_missing():
    payload = _make_payload()
    cog, _, thread_service = _make_cog(guild=None)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Guard: channel is not a TextChannel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_when_channel_not_text_channel():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    non_text_channel = MagicMock(spec=discord.VoiceChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=non_text_channel)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_when_channel_not_text_channel():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    non_text_channel = MagicMock(spec=discord.VoiceChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=non_text_channel)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Guard: member not found in cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_when_member_not_found():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    guild.get_member.return_value = None
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_when_member_not_found():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    guild.get_member.return_value = None
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Guard: member is a bot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_when_member_is_bot():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    guild.get_member.return_value = _make_member(is_bot=True)
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_when_member_is_bot():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    guild.get_member.return_value = _make_member(is_bot=True)
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path: delegates to ThreadService with the right arguments
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_delegates_to_thread_service():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    member = _make_member()
    guild.get_member.return_value = member
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_awaited_once_with(payload, guild, member)


@pytest.mark.asyncio
async def test_remove_delegates_to_thread_service():
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    member = _make_member()
    guild.get_member.return_value = member
    channel = MagicMock(spec=discord.TextChannel)
    cog, bot, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_awaited_once_with(payload, guild, bot)


# ---------------------------------------------------------------------------
# Feature flag disabled: ThreadService is not called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_skips_thread_service_when_event_threads_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.EVENT_THREADS] = False
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    member = _make_member()
    guild.get_member.return_value = member
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_add(payload)

    thread_service.add_reactor_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_remove_skips_thread_service_when_event_threads_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.EVENT_THREADS] = False
    payload = _make_payload()
    guild = MagicMock(spec=discord.Guild)
    member = _make_member()
    guild.get_member.return_value = member
    channel = MagicMock(spec=discord.TextChannel)
    cog, _, thread_service = _make_cog(guild=guild, channel=channel)

    await cog._handle_reaction_remove(payload)

    thread_service.remove_reactor_from_thread.assert_not_called()
