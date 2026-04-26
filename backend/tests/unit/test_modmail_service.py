"""Unit tests for the modmail service helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.services.modmail_service import (
    ModmailAmbiguousUserError,
    ModmailConfigError,
    ModmailService,
    ModmailUserNotFoundError,
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


def _fake_member(name: str, user_id: int) -> MagicMock:
    """Build a MagicMock that isinstance-passes as discord.abc.User."""
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.__str__ = lambda self: self.name  # type: ignore[assignment]
    return member


class TestResolveUser:
    """Tests for ModmailService.resolve_user."""

    @pytest.mark.asyncio
    async def test_passes_through_user_object(self):
        member = _fake_member("alice", 1)
        svc = ModmailService(bot=MagicMock())
        assert await svc.resolve_user(member) is member

    @pytest.mark.asyncio
    async def test_resolves_by_numeric_id_from_cache(self):
        member = _fake_member("alice", 42)
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=member)
        bot.fetch_user = AsyncMock()
        svc = ModmailService(bot=bot)
        assert await svc.resolve_user(42) is member
        bot.fetch_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolves_by_numeric_string_id(self):
        member = _fake_member("alice", 424242424242424242)
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(return_value=member)
        svc = ModmailService(bot=bot)
        assert await svc.resolve_user("424242424242424242") is member
        bot.fetch_user.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resolves_by_username_single_match(self):
        member = _fake_member("alice", 7)
        guild = MagicMock()
        guild.members = [member]
        bot = MagicMock()
        bot.guilds = [guild]
        svc = ModmailService(bot=bot)
        assert await svc.resolve_user("alice") is member

    @pytest.mark.asyncio
    async def test_username_not_found_raises(self):
        guild = MagicMock()
        guild.members = []
        bot = MagicMock()
        bot.guilds = [guild]
        svc = ModmailService(bot=bot)
        with pytest.raises(ModmailUserNotFoundError):
            await svc.resolve_user("nobody")

    @pytest.mark.asyncio
    async def test_username_ambiguous_raises(self):
        m1 = _fake_member("alice", 1)
        m2 = _fake_member("alice", 2)
        guild_a = MagicMock()
        guild_a.members = [m1]
        guild_b = MagicMock()
        guild_b.members = [m2]
        bot = MagicMock()
        bot.guilds = [guild_a, guild_b]
        svc = ModmailService(bot=bot)
        with pytest.raises(ModmailAmbiguousUserError):
            await svc.resolve_user("alice")

    @pytest.mark.asyncio
    async def test_accepts_leading_at(self):
        member = _fake_member("alice", 9)
        guild = MagicMock()
        guild.members = [member]
        bot = MagicMock()
        bot.guilds = [guild]
        svc = ModmailService(bot=bot)
        assert await svc.resolve_user("@alice") is member
