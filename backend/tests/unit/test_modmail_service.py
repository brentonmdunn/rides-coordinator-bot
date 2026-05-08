"""Unit tests for the modmail service helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from bot.services.modmail_service import (
    ModmailAmbiguousUserError,
    ModmailConfigError,
    ModmailDMForbiddenError,
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

    @pytest.mark.asyncio
    async def test_id_not_found_in_cache_fetches_remotely(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(), "not found"))
        svc = ModmailService(bot=bot)
        with pytest.raises(ModmailUserNotFoundError):
            await svc.resolve_user(999999999999999999)

    @pytest.mark.asyncio
    async def test_non_string_non_int_raises(self):
        svc = ModmailService(bot=MagicMock())
        with pytest.raises(ModmailUserNotFoundError):
            await svc.resolve_user(3.14)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_username_matches_by_str_representation(self):
        """Member whose str() is "alice#1234" matches when needle is "alice#1234"."""
        member = MagicMock(spec=discord.Member)
        member.id = 50
        member.name = "alice"
        member.__str__ = lambda self: "alice#1234"  # type: ignore[assignment]
        guild = MagicMock()
        guild.members = [member]
        bot = MagicMock()
        bot.guilds = [guild]
        svc = ModmailService(bot=bot)
        result = await svc.resolve_user("alice#1234")
        assert result is member


class TestBuildPermissions:
    """Tests for _build_permissions."""

    def test_default_role_denied(self):
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock()
        guild.get_role = MagicMock(return_value=None)
        # No admin roles
        admin_perms = MagicMock(spec=discord.Permissions)
        admin_perms.administrator = False
        role = MagicMock()
        role.permissions = admin_perms
        guild.roles = [role]

        svc = ModmailService(bot=MagicMock())
        overwrites = svc._build_permissions(guild)

        assert guild.default_role in overwrites
        assert overwrites[guild.default_role].read_messages is False

    def test_ride_coordinator_role_gets_access(self):
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock()
        ride_coord_role = MagicMock()
        guild.get_role = MagicMock(return_value=ride_coord_role)
        guild.roles = []

        svc = ModmailService(bot=MagicMock())
        overwrites = svc._build_permissions(guild)

        assert ride_coord_role in overwrites
        assert overwrites[ride_coord_role].read_messages is True
        assert overwrites[ride_coord_role].send_messages is True

    def test_admin_roles_get_access(self):
        guild = MagicMock(spec=discord.Guild)
        guild.default_role = MagicMock()
        guild.get_role = MagicMock(return_value=None)

        admin_perms = MagicMock(spec=discord.Permissions)
        admin_perms.administrator = True
        admin_role = MagicMock()
        admin_role.permissions = admin_perms
        guild.roles = [admin_role]

        svc = ModmailService(bot=MagicMock())
        overwrites = svc._build_permissions(guild)

        assert admin_role in overwrites
        assert overwrites[admin_role].read_messages is True
        assert overwrites[admin_role].send_messages is True


class TestGetCategory:
    """Extended tests for _get_category."""

    def test_valid_category_returned(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "500")
        category = MagicMock(spec=discord.CategoryChannel)
        guild = MagicMock()
        guild.name = "Test"
        guild.get_channel = MagicMock(return_value=category)
        svc = ModmailService(bot=MagicMock())
        assert svc._get_category(guild) is category


class TestPersistMessage:
    """Tests for _persist_message."""

    @pytest.mark.asyncio
    async def test_exception_is_logged_not_raised(self):
        """If DB operations fail, the exception is swallowed and logged."""
        svc = ModmailService(bot=MagicMock())

        from bot.core.enums import ModmailSenderType

        with patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session
            mock_session.commit.side_effect = RuntimeError("DB down")

            # Should not raise
            await svc._persist_message(
                user_id="123",
                sender_type=ModmailSenderType.USER,
                sender_id="123",
                sender_name="Alice",
                content="hello",
            )

    @pytest.mark.asyncio
    async def test_attachment_urls_serialized(self):
        """attachment_urls are JSON-serialized when provided."""
        svc = ModmailService(bot=MagicMock())

        from bot.core.enums import ModmailSenderType

        captured = {}

        with (
            patch("bot.services.modmail_service.ModmailMessagesRepository.create") as mock_create,
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
        ):
            fake_row = MagicMock()
            fake_row.id = 1
            fake_row.user_id = "123"
            fake_row.sender_type = ModmailSenderType.USER
            fake_row.sender_id = "123"
            fake_row.sender_name = "Alice"
            fake_row.content = "hello"
            fake_row.attachments_json = '["http://example.com/img.png"]'
            fake_row.created_at = MagicMock()
            fake_row.created_at.isoformat.return_value = "2024-01-01T00:00:00"
            mock_create.return_value = fake_row

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            with patch(
                "bot.services.modmail_service.modmail_ws_manager.broadcast"
            ) as mock_broadcast:
                mock_broadcast.return_value = None
                await svc._persist_message(
                    user_id="123",
                    sender_type=ModmailSenderType.USER,
                    sender_id="123",
                    sender_name="Alice",
                    content="hello",
                    attachment_urls=["http://example.com/img.png"],
                )
                captured["kwargs"] = mock_create.call_args

        import json

        _, kwargs = captured["kwargs"]
        assert kwargs["attachments_json"] == json.dumps(["http://example.com/img.png"])

    @pytest.mark.asyncio
    async def test_no_attachment_urls_passes_none(self):
        """When attachment_urls is None, attachments_json should be None."""
        svc = ModmailService(bot=MagicMock())

        from bot.core.enums import ModmailSenderType

        captured = {}

        with (
            patch("bot.services.modmail_service.ModmailMessagesRepository.create") as mock_create,
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
        ):
            fake_row = MagicMock()
            fake_row.id = 1
            fake_row.user_id = "123"
            fake_row.sender_type = ModmailSenderType.USER
            fake_row.sender_id = "123"
            fake_row.sender_name = "Alice"
            fake_row.content = "hello"
            fake_row.attachments_json = None
            fake_row.created_at = MagicMock()
            fake_row.created_at.isoformat.return_value = "2024-01-01T00:00:00"
            mock_create.return_value = fake_row

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            with patch("bot.services.modmail_service.modmail_ws_manager.broadcast"):
                await svc._persist_message(
                    user_id="123",
                    sender_type=ModmailSenderType.USER,
                    sender_id="123",
                    sender_name="Alice",
                    content="hello",
                    attachment_urls=None,
                )
                captured["kwargs"] = mock_create.call_args

        _, kwargs = captured["kwargs"]
        assert kwargs["attachments_json"] is None


class TestResolveUserRow:
    """Tests for _resolve_user_row."""

    @pytest.mark.asyncio
    async def test_returns_cached_user(self):
        user = MagicMock(spec=discord.User)
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=user)
        bot.fetch_user = AsyncMock()

        row = MagicMock()
        row.user_id = "123"

        svc = ModmailService(bot=bot)
        result = await svc._resolve_user_row(row)
        assert result is user
        bot.fetch_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetches_when_not_cached(self):
        user = MagicMock(spec=discord.User)
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(return_value=user)

        row = MagicMock()
        row.user_id = "456"

        svc = ModmailService(bot=bot)
        result = await svc._resolve_user_row(row)
        assert result is user

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        bot = MagicMock()
        bot.get_user = MagicMock(return_value=None)
        bot.fetch_user = AsyncMock(side_effect=discord.NotFound(MagicMock(), "not found"))

        row = MagicMock()
        row.user_id = "789"

        svc = ModmailService(bot=bot)
        result = await svc._resolve_user_row(row)
        assert result is None


class TestSendDm:
    """Tests for _send_dm."""

    @pytest.mark.asyncio
    async def test_sends_without_attachments(self):
        user = MagicMock(spec=discord.abc.User)
        user.send = AsyncMock()

        svc = ModmailService(bot=MagicMock())
        await svc._send_dm(user, "hello", None)
        user.send.assert_awaited_once_with(content="hello", files=None)

    @pytest.mark.asyncio
    async def test_forbidden_raises_modmail_error(self):
        user = MagicMock(spec=discord.abc.User)
        user.send = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "forbidden"))

        svc = ModmailService(bot=MagicMock())
        with pytest.raises(ModmailDMForbiddenError):
            await svc._send_dm(user, "hello", None)

    @pytest.mark.asyncio
    async def test_empty_content_sends_none(self):
        user = MagicMock(spec=discord.abc.User)
        user.send = AsyncMock()

        svc = ModmailService(bot=MagicMock())
        await svc._send_dm(user, "", None)
        user.send.assert_awaited_once_with(content=None, files=None)


class TestGetOrCreateChannel:
    """Tests for get_or_create_channel."""

    @pytest.mark.asyncio
    async def test_raises_when_no_guild_and_bot_in_multiple(self):
        bot = MagicMock()
        bot.guilds = [MagicMock(), MagicMock()]
        svc = ModmailService(bot=bot)

        user = MagicMock(spec=discord.abc.User)
        user.id = 1

        with pytest.raises(ModmailConfigError, match="none provided"):
            await svc.get_or_create_channel(user)

    @pytest.mark.asyncio
    async def test_returns_existing_channel_from_db(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 999

        guild = MagicMock(spec=discord.Guild)
        guild.id = 1
        guild.get_channel = MagicMock(return_value=channel)

        existing_row = MagicMock()
        existing_row.channel_id = "999"

        bot = MagicMock()
        bot.guilds = [guild]

        user = MagicMock(spec=discord.abc.User)
        user.id = 42

        svc = ModmailService(bot=bot)

        with (
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
            patch(
                "bot.services.modmail_service.ModmailRepository.get_by_user_id",
                new=AsyncMock(return_value=existing_row),
            ),
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            result = await svc.get_or_create_channel(user, guild=guild)
            assert result is channel


class TestDmUser:
    """Tests for dm_user."""

    @pytest.mark.asyncio
    async def test_returns_delivered_true_on_success(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        user = MagicMock(spec=discord.abc.User)
        user.id = 77
        user.mention = "<@77>"
        user.display_avatar = MagicMock()
        user.display_avatar.url = "http://avatar.png"
        user.__str__ = lambda self: "staffuser"  # type: ignore[assignment]

        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()

        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 1
        bot.user.__str__ = lambda self: "Bot"  # type: ignore[assignment]
        bot.user.display_avatar = None

        svc = ModmailService(bot=bot)

        with (
            patch.object(svc, "resolve_user", new=AsyncMock(return_value=user)),
            patch.object(svc, "get_or_create_channel", new=AsyncMock(return_value=channel)),
            patch.object(svc, "_send_dm", new=AsyncMock()),
            patch.object(svc, "_persist_message", new=AsyncMock()),
        ):
            result = await svc.dm_user(user, "hello world")

        assert result.delivered is True
        assert result.channel is channel

    @pytest.mark.asyncio
    async def test_returns_delivered_false_when_dm_forbidden(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        user = MagicMock(spec=discord.abc.User)
        user.id = 77
        user.mention = "<@77>"
        user.display_avatar = None
        user.__str__ = lambda self: "someuser"  # type: ignore[assignment]

        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()

        bot = MagicMock()
        bot.user = None

        svc = ModmailService(bot=bot)

        with (
            patch.object(svc, "resolve_user", new=AsyncMock(return_value=user)),
            patch.object(svc, "get_or_create_channel", new=AsyncMock(return_value=channel)),
            patch.object(
                svc, "_send_dm", new=AsyncMock(side_effect=ModmailDMForbiddenError("blocked"))
            ),
            patch.object(svc, "_persist_message", new=AsyncMock()),
        ):
            result = await svc.dm_user(user, "hello")

        assert result.delivered is False
        assert result.channel is channel


class TestRelayDmToChannel:
    """Tests for relay_dm_to_channel."""

    @pytest.mark.asyncio
    async def test_posts_embed_and_persists(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        user = MagicMock(spec=discord.Member)
        user.id = 55
        user.display_avatar = MagicMock()
        user.display_avatar.url = "http://img"
        user.__str__ = lambda self: "testuser"  # type: ignore[assignment]

        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()

        message = MagicMock(spec=discord.Message)
        message.author = user
        message.content = "Hello staff!"
        message.attachments = []
        message.created_at = None

        svc = ModmailService(bot=MagicMock())

        with (
            patch.object(svc, "get_or_create_channel", new=AsyncMock(return_value=channel)),
            patch.object(svc, "_persist_message", new=AsyncMock()) as mock_persist,
        ):
            await svc.relay_dm_to_channel(message)

        channel.send.assert_awaited_once()
        mock_persist.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_config_error_is_handled_gracefully(self):
        user = MagicMock(spec=discord.Member)
        user.id = 55

        message = MagicMock(spec=discord.Message)
        message.author = user
        message.content = "hey"
        message.attachments = []

        svc = ModmailService(bot=MagicMock())

        with (
            patch.object(
                svc,
                "get_or_create_channel",
                new=AsyncMock(side_effect=ModmailConfigError("not configured")),
            ),
            patch("bot.services.modmail_service.send_error_to_discord", new=AsyncMock()),
        ):
            # Should not raise
            await svc.relay_dm_to_channel(message)

    @pytest.mark.asyncio
    async def test_includes_attachment_urls_in_embed(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        user = MagicMock(spec=discord.Member)
        user.id = 55
        user.display_avatar = None
        user.__str__ = lambda self: "testuser"  # type: ignore[assignment]

        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()

        att = MagicMock()
        att.url = "http://example.com/file.png"

        message = MagicMock(spec=discord.Message)
        message.author = user
        message.content = ""
        message.attachments = [att]
        message.created_at = None

        svc = ModmailService(bot=MagicMock())

        with (
            patch.object(svc, "get_or_create_channel", new=AsyncMock(return_value=channel)),
            patch.object(svc, "_persist_message", new=AsyncMock()) as mock_persist,
        ):
            await svc.relay_dm_to_channel(message)

        # persist_message should be called with the attachment URL
        call_kwargs = mock_persist.call_args.kwargs
        assert call_kwargs["attachment_urls"] == ["http://example.com/file.png"]


class TestRelayChannelToDm:
    """Tests for relay_channel_to_dm."""

    @pytest.mark.asyncio
    async def test_skips_non_text_channel(self):
        message = MagicMock(spec=discord.Message)
        message.channel = MagicMock(spec=discord.DMChannel)

        svc = ModmailService(bot=MagicMock())
        # Should not raise or do anything
        await svc.relay_channel_to_dm(message)

    @pytest.mark.asyncio
    async def test_skips_wrong_category(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.category_id = 999  # Wrong category

        message = MagicMock(spec=discord.Message)
        message.channel = channel

        svc = ModmailService(bot=MagicMock())
        await svc.relay_channel_to_dm(message)

    @pytest.mark.asyncio
    async def test_skips_when_no_db_row(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 200
        channel.category_id = 100

        message = MagicMock(spec=discord.Message)
        message.channel = channel

        svc = ModmailService(bot=MagicMock())

        with (
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
            patch(
                "bot.services.modmail_service.ModmailRepository.get_by_channel_id",
                new=AsyncMock(return_value=None),
            ),
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            await svc.relay_channel_to_dm(message)

    @pytest.mark.asyncio
    async def test_posts_warning_when_user_unresolvable(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 200
        channel.category_id = 100
        channel.send = AsyncMock()

        message = MagicMock(spec=discord.Message)
        message.channel = channel

        row = MagicMock()
        row.user_id = "111"

        svc = ModmailService(bot=MagicMock())

        with (
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
            patch(
                "bot.services.modmail_service.ModmailRepository.get_by_channel_id",
                new=AsyncMock(return_value=row),
            ),
            patch.object(svc, "_resolve_user_row", new=AsyncMock(return_value=None)),
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            await svc.relay_channel_to_dm(message)

        channel.send.assert_awaited_once()
        embed_sent = (
            channel.send.call_args.kwargs.get("embed") or channel.send.call_args.args[0]
            if channel.send.call_args.args
            else None
        )
        # Just ensure a send happened with an embed (warning embed)
        assert channel.send.await_count == 1

    @pytest.mark.asyncio
    async def test_relay_sends_dm_and_confirmation(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 200
        channel.category_id = 100
        channel.send = AsyncMock()

        user = MagicMock(spec=discord.User)
        user.id = 77
        user.mention = "<@77>"
        user.__str__ = lambda self: "targetuser"  # type: ignore[assignment]

        author = MagicMock()
        author.id = 5
        author.display_avatar = None
        author.__str__ = lambda self: "staffmember"  # type: ignore[assignment]

        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.content = "Hello!"
        message.attachments = []
        message.author = author
        message.created_at = None
        message.delete = AsyncMock()

        row = MagicMock()
        row.user_id = "77"

        svc = ModmailService(bot=MagicMock())

        with (
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
            patch(
                "bot.services.modmail_service.ModmailRepository.get_by_channel_id",
                new=AsyncMock(return_value=row),
            ),
            patch.object(svc, "_resolve_user_row", new=AsyncMock(return_value=user)),
            patch.object(svc, "_send_dm", new=AsyncMock()),
            patch.object(svc, "_persist_message", new=AsyncMock()) as mock_persist,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            await svc.relay_channel_to_dm(message)

        channel.send.assert_awaited_once()
        mock_persist.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dm_forbidden_posts_warning(self, monkeypatch):
        monkeypatch.setenv("MODMAIL_CATEGORY_ID", "100")

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 200
        channel.category_id = 100
        channel.send = AsyncMock()

        user = MagicMock(spec=discord.User)
        user.id = 77
        user.mention = "<@77>"

        author = MagicMock()
        author.id = 5
        message = MagicMock(spec=discord.Message)
        message.channel = channel
        message.content = "DM this!"
        message.attachments = []
        message.author = author

        row = MagicMock()
        row.user_id = "77"

        svc = ModmailService(bot=MagicMock())

        with (
            patch("bot.services.modmail_service.AsyncSessionLocal") as mock_ctx,
            patch(
                "bot.services.modmail_service.ModmailRepository.get_by_channel_id",
                new=AsyncMock(return_value=row),
            ),
            patch.object(svc, "_resolve_user_row", new=AsyncMock(return_value=user)),
            patch.object(
                svc,
                "_send_dm",
                new=AsyncMock(side_effect=ModmailDMForbiddenError("blocked")),
            ),
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.return_value = mock_session

            await svc.relay_channel_to_dm(message)

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_config_error_skips_silently(self, monkeypatch):
        monkeypatch.delenv("MODMAIL_CATEGORY_ID", raising=False)

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 200
        channel.category_id = None  # Doesn't matter, config will fail first

        message = MagicMock(spec=discord.Message)
        message.channel = channel

        svc = ModmailService(bot=MagicMock())
        # Should return silently without raising
        await svc.relay_channel_to_dm(message)
