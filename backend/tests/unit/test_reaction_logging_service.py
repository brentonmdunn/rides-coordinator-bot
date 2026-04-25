"""Unit tests for bot.services.reaction_logging_service."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.core.enums import ReactionAction
from bot.services.reaction_logging_service import ReactionLoggingService


def _make_user(name="testuser"):
    user = MagicMock(spec=discord.Member)
    user.name = name
    return user


def _make_payload(emoji="👍"):
    payload = MagicMock(spec=discord.RawReactionActionEvent)
    payload.emoji = emoji
    return payload


def _make_message(content="Test message", message_id=100):
    msg = MagicMock(spec=discord.Message)
    msg.content = content
    msg.id = message_id
    msg.embeds = []
    return msg


def _make_channel(channel_id=200, guild_id=300):
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = channel_id
    channel.guild = MagicMock()
    channel.guild.id = guild_id
    return channel


class TestFormatReactionLog:
    """Tests for _format_reaction_log."""

    def test_add_action(self):
        svc = ReactionLoggingService(bot=None)
        user = _make_user("alice")
        payload = _make_payload("🚗")
        message = _make_message("Hello")
        channel = _make_channel()

        result = svc._format_reaction_log(user, payload, message, channel, ReactionAction.ADD)
        assert "alice" in result
        assert "reacted" in result
        assert "🚗" in result

    def test_remove_action(self):
        svc = ReactionLoggingService(bot=None)
        user = _make_user("bob")
        payload = _make_payload("🍔")
        message = _make_message("Hi")
        channel = _make_channel()

        result = svc._format_reaction_log(user, payload, message, channel, ReactionAction.REMOVE)
        assert "bob" in result
        assert "removed their reaction" in result

    def test_invalid_action_raises(self):
        svc = ReactionLoggingService(bot=None)
        with pytest.raises(ValueError, match="Invalid action"):
            svc._format_reaction_log(
                _make_user(), _make_payload(), _make_message(), _make_channel(), "invalid"
            )

    def test_empty_content_shows_placeholder(self):
        svc = ReactionLoggingService(bot=None)
        message = _make_message(content="")
        message.content = ""

        result = svc._format_reaction_log(
            _make_user(), _make_payload(), message, _make_channel(), ReactionAction.ADD
        )
        assert "[No Content/Embed]" in result

    def test_message_link_in_result(self):
        svc = ReactionLoggingService(bot=None)
        channel = _make_channel(guild_id=111, channel_id=222)
        message = _make_message(message_id=333)

        result = svc._format_reaction_log(
            _make_user(), _make_payload(), message, channel, ReactionAction.ADD
        )
        assert "discord.com/channels/111/222/333" in result


class TestFormatReactionLogLateRides:
    """Tests for _format_reaction_log_late_rides."""

    def test_friday_message(self):
        svc = ReactionLoggingService(bot=None)
        message = _make_message("React for Friday fellowship 4/24")

        result = svc._format_reaction_log_late_rides(
            _make_user("alice"), _make_payload(), message, ReactionAction.ADD
        )
        assert "Friday Fellowship" in result
        assert "reacted" in result

    def test_sunday_message(self):
        svc = ReactionLoggingService(bot=None)
        message = _make_message("React for Sunday service 4/26")

        result = svc._format_reaction_log_late_rides(
            _make_user(), _make_payload(), message, ReactionAction.ADD
        )
        assert "Sunday Service" in result

    def test_unknown_message(self):
        svc = ReactionLoggingService(bot=None)
        message = _make_message("Something random")

        result = svc._format_reaction_log_late_rides(
            _make_user(), _make_payload(), message, ReactionAction.ADD
        )
        assert "unknown message" in result

    def test_remove_action(self):
        svc = ReactionLoggingService(bot=None)
        message = _make_message("React for Friday")

        result = svc._format_reaction_log_late_rides(
            _make_user(), _make_payload(), message, ReactionAction.REMOVE
        )
        assert "removed their reaction" in result

    def test_invalid_action_raises(self):
        svc = ReactionLoggingService(bot=None)
        with pytest.raises(ValueError, match="Invalid action"):
            svc._format_reaction_log_late_rides(
                _make_user(), _make_payload(), _make_message(), "bad"
            )


class TestLogReaction:
    """Tests for log_reaction."""

    @pytest.mark.asyncio
    async def test_returns_false_if_no_log_channel(self):
        bot = MagicMock()
        bot.get_channel.return_value = None
        svc = ReactionLoggingService(bot=bot)

        result = await svc.log_reaction(
            _make_user(), _make_payload(), _make_message(), _make_channel(), ReactionAction.ADD
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_to_log_channel(self):
        log_channel = AsyncMock(spec=discord.TextChannel)
        bot = MagicMock()
        bot.get_channel.return_value = log_channel
        svc = ReactionLoggingService(bot=bot)

        result = await svc.log_reaction(
            _make_user(), _make_payload(), _make_message(), _make_channel(), ReactionAction.ADD
        )
        assert result is True
        log_channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_on_forbidden(self):
        log_channel = AsyncMock(spec=discord.TextChannel)
        log_channel.send.side_effect = discord.Forbidden(MagicMock(), "forbidden")
        log_channel.id = 999
        bot = MagicMock()
        bot.get_channel.return_value = log_channel
        svc = ReactionLoggingService(bot=bot)

        result = await svc.log_reaction(
            _make_user(), _make_payload(), _make_message(), _make_channel(), ReactionAction.ADD
        )
        assert result is False


class TestLogLateRideReaction:
    """Tests for log_late_ride_reaction."""

    @pytest.mark.asyncio
    async def test_returns_false_if_no_channel(self):
        bot = MagicMock()
        bot.get_channel.return_value = None
        svc = ReactionLoggingService(bot=bot)

        result = await svc.log_late_ride_reaction(
            _make_user(), _make_payload(), _make_message(), ReactionAction.ADD
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_to_driver_bot_spam(self):
        log_channel = AsyncMock(spec=discord.TextChannel)
        bot = MagicMock()
        bot.get_channel.return_value = log_channel
        svc = ReactionLoggingService(bot=bot)

        result = await svc.log_late_ride_reaction(
            _make_user(), _make_payload(), _make_message("Friday rides"), ReactionAction.ADD
        )
        assert result is True
        log_channel.send.assert_awaited_once()
