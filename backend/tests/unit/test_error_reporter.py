"""Unit tests for bot.core.error_reporter."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from bot.core.error_reporter import _get_config, send_error_to_discord

_ENABLED = "bot.core.error_reporter._is_send_errors_enabled"


class TestGetConfig:
    """Tests for _get_config."""

    @patch.dict("os.environ", {"APP_ENV": "production", "ERROR_CHANNEL_ID": "123"})
    def test_production_with_channel(self):
        env, channel_id = _get_config()
        assert env == "production"
        assert channel_id == 123

    @patch.dict("os.environ", {"APP_ENV": "local"}, clear=False)
    def test_local_env(self):
        env, _ = _get_config()
        assert env == "local"

    @patch.dict("os.environ", {}, clear=True)
    def test_defaults(self):
        env, channel_id = _get_config()
        assert env == "local"
        assert channel_id is None


class TestSendErrorToDiscord:
    """Tests for send_error_to_discord."""

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("local", 123))
    async def test_skips_in_local_env(self, mock_config):
        # Should return early without sending
        await send_error_to_discord("test error")
        # No exception means success

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", None))
    async def test_skips_when_no_channel_id(self, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=False)
    async def test_skips_when_flag_disabled(self, mock_flag, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot", return_value=None)
    async def test_skips_when_bot_not_ready(self, mock_bot, mock_flag, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_sends_error_message(self, mock_get_bot, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_get_bot.return_value = mock_bot

        await send_error_to_discord("Something broke")

        mock_channel.send.assert_awaited_once()
        sent_msg = mock_channel.send.call_args[0][0]
        assert "Something broke" in sent_msg

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_sends_error_with_traceback(self, mock_get_bot, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_get_bot.return_value = mock_bot

        try:
            raise ValueError("test exception")
        except ValueError as e:
            await send_error_to_discord("Error occurred", error=e)

        mock_channel.send.assert_awaited()

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_sends_error_with_explicit_traceback(self, mock_get_bot, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_get_bot.return_value = mock_bot

        await send_error_to_discord("Error", tb_text="Traceback: line 1")
        mock_channel.send.assert_awaited()

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_long_traceback_chunked(self, mock_get_bot, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_get_bot.return_value = mock_bot

        long_tb = "x" * 3000
        await send_error_to_discord("Error", tb_text=long_tb)
        # Should be called more than once (message + chunk(s))
        assert mock_channel.send.await_count >= 2

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_channel_not_text_channel(self, mock_get_bot, mock_flag, mock_config):
        mock_channel = MagicMock()  # Not a TextChannel
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_get_bot.return_value = mock_bot

        # Should not crash
        await send_error_to_discord("Error")

    @pytest.mark.asyncio
    @patch("bot.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("bot.core.error_reporter.get_bot")
    async def test_channel_not_found(self, mock_get_bot, mock_flag, mock_config):
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = None
        mock_get_bot.return_value = mock_bot

        await send_error_to_discord("Error")
