"""Unit tests for shared.core.error_reporter."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from shared.core.enums import BotName
from shared.core.error_reporter import _get_config, _pick_reporting_bot, send_error_to_discord

_ENABLED = "shared.core.error_reporter._is_send_errors_enabled"
_PICK = "shared.core.error_reporter._pick_reporting_bot"


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


class TestPickReportingBot:
    """Tests for _pick_reporting_bot."""

    @patch("shared.core.error_reporter.get_ready_bots", return_value={})
    @patch("shared.core.error_reporter.get_bot")
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=BotName.RIDEBOT)
    def test_origin_ready(self, mock_current, mock_get_bot, mock_ready):
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        result = _pick_reporting_bot()

        assert result is mock_bot
        mock_get_bot.assert_any_call(BotName.RIDEBOT)

    @patch("shared.core.error_reporter.get_ready_bots", return_value={})
    @patch("shared.core.error_reporter.get_bot")
    @patch("shared.core.error_reporter.get_current_bot_name", return_value="otherbot")
    def test_origin_not_ready_falls_back_to_registry(self, mock_current, mock_get_bot, mock_ready):
        mock_ridebot = MagicMock()

        def side_effect(name):
            if name == BotName.RIDEBOT:
                return mock_ridebot
            return None

        mock_get_bot.side_effect = side_effect

        result = _pick_reporting_bot()

        assert result is mock_ridebot

    @patch("shared.core.error_reporter.get_ready_bots", return_value={})
    @patch("shared.core.error_reporter.get_bot")
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    def test_no_origin_uses_registry(self, mock_current, mock_get_bot, mock_ready):
        mock_ridebot = MagicMock()
        mock_get_bot.return_value = mock_ridebot

        result = _pick_reporting_bot()

        assert result is mock_ridebot
        mock_get_bot.assert_any_call(BotName.RIDEBOT)

    @patch("shared.core.error_reporter.get_ready_bots", return_value={})
    @patch("shared.core.error_reporter.get_bot", return_value=None)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    def test_none_ready_returns_none(self, mock_current, mock_get_bot, mock_ready):
        assert _pick_reporting_bot() is None

    @patch("shared.core.error_reporter.get_bot", return_value=None)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    def test_falls_back_to_any_ready_bot(self, mock_current, mock_get_bot):
        mock_other = MagicMock()
        with patch(
            "shared.core.error_reporter.get_ready_bots",
            return_value={BotName.RIDEBOT: mock_other},
        ):
            assert _pick_reporting_bot() is mock_other


class TestSendErrorToDiscord:
    """Tests for send_error_to_discord."""

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("local", 123))
    async def test_skips_in_local_env(self, mock_config):
        # Should return early without sending
        await send_error_to_discord("test error")
        # No exception means success

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", None))
    async def test_skips_when_no_channel_id(self, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=False)
    async def test_skips_when_flag_disabled(self, mock_flag, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK, return_value=None)
    async def test_skips_when_bot_not_ready(self, mock_pick, mock_current, mock_flag, mock_config):
        await send_error_to_discord("test error")

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_sends_error_message(self, mock_pick, mock_current, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        await send_error_to_discord("Something broke")

        mock_channel.send.assert_awaited_once()
        sent_msg = mock_channel.send.call_args[0][0]
        assert "Something broke" in sent_msg

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=BotName.RIDEBOT)
    @patch(_PICK)
    async def test_prefixes_message_when_origin_set(
        self, mock_pick, mock_current, mock_flag, mock_config
    ):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        await send_error_to_discord("Something broke")

        sent_msg = mock_channel.send.call_args[0][0]
        assert sent_msg.startswith("[ridebot] Something broke")

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_no_prefix_when_no_origin(self, mock_pick, mock_current, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        await send_error_to_discord("Something broke")

        sent_msg = mock_channel.send.call_args[0][0]
        assert sent_msg == "Something broke"

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_sends_error_with_traceback(
        self, mock_pick, mock_current, mock_flag, mock_config
    ):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        try:
            raise ValueError("test exception")
        except ValueError as e:
            await send_error_to_discord("Error occurred", error=e)

        mock_channel.send.assert_awaited()

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_sends_error_with_explicit_traceback(
        self, mock_pick, mock_current, mock_flag, mock_config
    ):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        await send_error_to_discord("Error", tb_text="Traceback: line 1")
        mock_channel.send.assert_awaited()

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_long_traceback_chunked(self, mock_pick, mock_current, mock_flag, mock_config):
        mock_channel = AsyncMock(spec=discord.TextChannel)
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        long_tb = "x" * 3000
        await send_error_to_discord("Error", tb_text=long_tb)
        # Should be called more than once (message + chunk(s))
        assert mock_channel.send.await_count >= 2

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_channel_not_text_channel(self, mock_pick, mock_current, mock_flag, mock_config):
        mock_channel = MagicMock()  # Not a TextChannel
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = mock_channel
        mock_pick.return_value = mock_bot

        # Should not crash
        await send_error_to_discord("Error")

    @pytest.mark.asyncio
    @patch("shared.core.error_reporter._get_config", return_value=("production", 123))
    @patch(_ENABLED, return_value=True)
    @patch("shared.core.error_reporter.get_current_bot_name", return_value=None)
    @patch(_PICK)
    async def test_channel_not_found(self, mock_pick, mock_current, mock_flag, mock_config):
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = None
        mock_pick.return_value = mock_bot

        await send_error_to_discord("Error")
