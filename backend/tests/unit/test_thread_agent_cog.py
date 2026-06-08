"""Unit tests for the ThreadAgent cog (#general thread-maker)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

os.environ.setdefault("TRITON_API_KEY", "test")

from agent.thread_intent import SOURCE_ABOVE, SOURCE_CLARIFY, SOURCE_REPLIED
from bot.cogs.thread_agent import _ALLOWED_CHANNEL_IDS, ThreadAgent

_CHANNEL_ID = next(iter(_ALLOWED_CHANNEL_IDS))
_OTHER_CHANNEL_ID = max(_ALLOWED_CHANNEL_IDS) + 1

pytestmark = pytest.mark.asyncio


async def _aiter(items):
    for item in items:
        yield item


def _make_cog():
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 1
    service = MagicMock()
    service.create_event_thread_from_message = AsyncMock(return_value=(MagicMock(), [], []))
    return ThreadAgent(bot, service), bot, service


def _make_message(bot, *, channel_id=_CHANNEL_ID, mentions_bot=True, content="@bot thread this"):
    message = MagicMock(spec=discord.Message)
    message.author = MagicMock()
    message.author.bot = False
    message.author.id = 42
    message.author.display_name = "Tester"
    message.channel = MagicMock()
    message.channel.id = channel_id
    message.mentions = [bot.user] if mentions_bot else []
    message.content = content
    message.reference = None
    message.add_reaction = AsyncMock()
    message.reply = AsyncMock()
    return message


def _enable_flag(value=True):
    return patch.object(
        ThreadAgent, "_is_feature_enabled", new_callable=AsyncMock, return_value=value
    )


async def test_ignores_other_channel():
    cog, bot, service = _make_cog()
    message = _make_message(bot, channel_id=_OTHER_CHANNEL_ID)
    await cog.on_message(message)
    service.create_event_thread_from_message.assert_not_called()


async def test_ignores_message_without_mention():
    cog, bot, service = _make_cog()
    message = _make_message(bot, mentions_bot=False)
    await cog.on_message(message)
    service.create_event_thread_from_message.assert_not_called()


async def test_ignores_bot_author():
    cog, bot, service = _make_cog()
    message = _make_message(bot)
    message.author.bot = True
    await cog.on_message(message)
    service.create_event_thread_from_message.assert_not_called()


async def test_ignores_when_flag_disabled():
    cog, bot, service = _make_cog()
    message = _make_message(bot)
    with _enable_flag(False):
        await cog.on_message(message)
    service.create_event_thread_from_message.assert_not_called()


async def test_reply_intent_creates_thread_and_reacts():
    cog, bot, service = _make_cog()
    message = _make_message(bot)
    replied = MagicMock(spec=discord.Message)
    replied.author = MagicMock()
    replied.author.display_name = "Author"
    replied.content = "carpool sunday"
    message.reference = MagicMock()
    message.reference.message_id = 100
    message.reference.resolved = replied

    with (
        _enable_flag(),
        patch(
            "bot.cogs.thread_agent.classify_thread_intent",
            return_value=(SOURCE_REPLIED, None),
        ),
    ):
        await cog.on_message(message)

    service.create_event_thread_from_message.assert_awaited_once()
    target_arg = service.create_event_thread_from_message.call_args.args[0]
    assert target_arg is replied
    message.add_reaction.assert_awaited_once_with("✅")


async def test_above_intent_picks_previous_non_bot_message():
    cog, bot, service = _make_cog()
    message = _make_message(bot)

    bot_msg = MagicMock(spec=discord.Message)
    bot_msg.author = MagicMock()
    bot_msg.author.id = bot.user.id  # bot's own — should be skipped
    above = MagicMock(spec=discord.Message)
    above.author = MagicMock()
    above.author.id = 7
    above.author.display_name = "Someone"
    above.content = "anyone going friday"
    message.channel.history = MagicMock(return_value=_aiter([bot_msg, above]))

    with (
        _enable_flag(),
        patch(
            "bot.cogs.thread_agent.classify_thread_intent",
            return_value=(SOURCE_ABOVE, None),
        ),
    ):
        await cog.on_message(message)

    target_arg = service.create_event_thread_from_message.call_args.args[0]
    assert target_arg is above
    message.add_reaction.assert_awaited_once_with("✅")


async def test_clarify_intent_replies_and_skips_service():
    cog, bot, service = _make_cog()
    message = _make_message(bot)

    with (
        _enable_flag(),
        patch(
            "bot.cogs.thread_agent.classify_thread_intent",
            return_value=(SOURCE_CLARIFY, "Reply to the message you want threaded."),
        ),
    ):
        await cog.on_message(message)

    service.create_event_thread_from_message.assert_not_called()
    message.reply.assert_awaited_once()
    assert "Reply to the message" in message.reply.call_args.args[0]


async def test_reply_intent_with_unresolvable_target_falls_back_to_clarify():
    cog, bot, service = _make_cog()
    message = _make_message(bot)
    message.reference = None  # reply intent but nothing to resolve

    with (
        _enable_flag(),
        patch(
            "bot.cogs.thread_agent.classify_thread_intent",
            return_value=(SOURCE_REPLIED, None),
        ),
    ):
        await cog.on_message(message)

    service.create_event_thread_from_message.assert_not_called()
    message.reply.assert_awaited_once()
