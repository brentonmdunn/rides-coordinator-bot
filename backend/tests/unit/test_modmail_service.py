"""Unit tests for the modmail service helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from bot.services.modmail_service import (
    ModmailConfigError,
    ModmailService,
    _channel_name_for,
    _sanitize_username,
)


class TestSanitizeUsername:
    """Tests for _sanitize_username."""

    def test_lowercases_input(self):
        assert _sanitize_username("FooBar") == "foobar"

    def test_replaces_invalid_chars(self):
        assert _sanitize_username("foo.bar baz") == "foo-bar-baz"

    def test_strips_trailing_dashes(self):
        assert _sanitize_username("...foo...") == "foo"

    def test_preserves_underscores_and_digits(self):
        assert _sanitize_username("user_123") == "user_123"

    def test_empty_falls_back(self):
        assert _sanitize_username("!!!") == "user"


class TestChannelNameFor:
    """Tests for _channel_name_for."""

    def test_includes_prefix_and_id(self):
        user = SimpleNamespace(id=12345, name="Alice")
        assert _channel_name_for(user) == "dm-alice-12345"

    def test_truncates_long_names(self):
        user = SimpleNamespace(id=1, name="x" * 200)
        assert len(_channel_name_for(user)) <= 90


class TestGetCategoryId:
    """Tests for reading MODMAIL_CATEGORY_ID from the environment."""

    def test_missing_raises(self, monkeypatch):
        monkeypatch.delenv("MODMAIL_CATEGORY_ID", raising=False)
        svc = ModmailService(bot=MagicMock())
        with pytest.raises(ModmailConfigError):
            svc._get_category_id()

    def test_invalid_raises(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "not-an-int")
        svc = ModmailService(bot=MagicMock())
        with pytest.raises(ModmailConfigError):
            svc._get_category_id()

    def test_valid_parses(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "987654321")
        svc = ModmailService(bot=MagicMock())
        assert svc._get_category_id() == 987654321


class TestGetCategory:
    """Tests for _get_category guild-resolution."""

    def test_non_category_raises(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "111")
        guild = MagicMock()
        guild.name = "Test"
        # get_channel returns something that isn't a CategoryChannel
        guild.get_channel = MagicMock(return_value=object())
        svc = ModmailService(bot=MagicMock())
        with pytest.raises(ModmailConfigError):
            svc._get_category(guild)


class TestPrimaryGuild:
    """Tests for _primary_guild single-guild resolution."""

    def test_single_guild(self):
        guild = MagicMock()
        bot = MagicMock()
        bot.guilds = [guild]
        svc = ModmailService(bot=bot)
        assert svc._primary_guild() is guild

    def test_multiple_guilds_returns_none(self):
        bot = MagicMock()
        bot.guilds = [MagicMock(), MagicMock()]
        svc = ModmailService(bot=bot)
        assert svc._primary_guild() is None

    def test_no_guild_returns_none(self):
        bot = MagicMock()
        bot.guilds = []
        svc = ModmailService(bot=bot)
        assert svc._primary_guild() is None
