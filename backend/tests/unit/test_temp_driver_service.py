"""Unit tests for TempDriverService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.services.temp_driver_service import (
    TempDriverEvent,
    TempDriverService,
    build_announcement,
)
from shared.core.enums import RoleIds

MODULE = "ridebot.services.temp_driver_service"


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session
    return mock_session


def _make_role(has_role_members=None):
    role = MagicMock(spec=discord.Role)
    role.id = int(RoleIds.DRIVER)
    return role


def _make_member(user_id=111, name="alice", display_name="Alice", roles=None):
    member = MagicMock(spec=discord.Member)
    member.id = user_id
    member.name = name
    member.display_name = display_name
    member.roles = roles or []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    return member


def _make_guild(member=None, role=None, member_named=None):
    guild = MagicMock(spec=discord.Guild)
    guild.get_role.return_value = role
    guild.get_member.return_value = member
    guild.get_member_named.return_value = member_named if member_named is not None else member
    return guild


def _make_bot(guild):
    bot = MagicMock()
    bot.get_guild.return_value = guild
    return bot


def _make_grant_row(discord_user_id="111", expires_at=None, granted_by="coordinator"):
    row = MagicMock()
    row.discord_user_id = discord_user_id
    row.discord_username = "alice"
    row.expires_at = expires_at or datetime(2026, 1, 1)
    row.granted_by = granted_by
    return row


class TestBuildAnnouncement:
    def _expires_at(self):
        return datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC)  # 11:59 PM PDT

    def test_granted(self):
        text = build_announcement(TempDriverEvent.GRANTED, "Alice", self._expires_at(), "Bob")
        assert text.startswith("🚗 **@Alice** is a temporary driver until **")
        assert "— added by Bob" in text
        assert "<t:" in text

    def test_extended_includes_previous(self):
        prev = self._expires_at() - timedelta(days=3)
        text = build_announcement(
            TempDriverEvent.EXTENDED, "Alice", self._expires_at(), "Bob", prev
        )
        assert "now ends **" in text
        assert "was " in text
        assert "— updated by Bob" in text

    def test_revoked(self):
        text = build_announcement(TempDriverEvent.REVOKED, "Alice", self._expires_at(), "Bob")
        assert text == "🚗 **@Alice**'s temporary Driver role was removed early by Bob"

    def test_expired(self):
        text = build_announcement(TempDriverEvent.EXPIRED, "Alice", self._expires_at(), "Bob")
        assert text == "🚗 **@Alice**'s temporary Driver role expired (granted by Bob)"

    def test_never_pings_with_id_mention(self):
        text = build_announcement(TempDriverEvent.GRANTED, "Alice", self._expires_at(), "Bob")
        assert "<@" not in text


class TestResolveMember:
    def test_found(self):
        member = _make_member()
        guild = _make_guild(member_named=member)
        service = TempDriverService(_make_bot(guild))

        result = service.resolve_member("alice")

        assert result is member
        guild.get_member_named.assert_called_once_with("alice")

    def test_strips_at_symbol(self):
        member = _make_member()
        guild = _make_guild(member_named=member)
        service = TempDriverService(_make_bot(guild))

        service.resolve_member("@Alice")

        guild.get_member_named.assert_called_once_with("alice")

    def test_not_found_raises(self):
        guild = _make_guild(member_named=None)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(ValueError, match="not found in server"):
            service.resolve_member("ghost")

    def test_guild_unavailable_raises(self):
        bot = MagicMock()
        bot.get_guild.return_value = None
        service = TempDriverService(bot)

        with pytest.raises(ValueError, match="Guild not available"):
            service.resolve_member("alice")


class TestGrant:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.upsert", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_new_user(self, mock_session_local, mock_get, mock_upsert):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        role = _make_role()
        member = _make_member(roles=[])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.grant(member, "3d", "coordinator@example.com")

        assert result.event == TempDriverEvent.GRANTED
        assert result.previous_expires_at is None
        member.add_roles.assert_awaited_once()
        mock_upsert.assert_awaited_once()
        service.announce.assert_awaited_once_with(result.announcement)

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.upsert", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_extends_existing(self, mock_session_local, mock_get, mock_upsert):
        _mock_session_local(mock_session_local)
        existing = _make_grant_row(expires_at=datetime(2026, 1, 1))
        mock_get.return_value = existing

        role = _make_role()
        member = _make_member(roles=[role])  # already has the role (temp)
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.grant(member, "3d", "coordinator@example.com")

        assert result.event == TempDriverEvent.EXTENDED
        assert result.previous_expires_at is not None
        member.add_roles.assert_not_called()  # already has the role
        mock_upsert.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_rejects_permanent_driver(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None  # no grant row

        role = _make_role()
        member = _make_member(roles=[role])  # has the role permanently
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(ValueError, match="already has the Driver role permanently"):
            await service.grant(member, "3d", "coordinator@example.com")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_forbidden_becomes_permission_error(self, mock_session_local, mock_get):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        role = _make_role()
        member = _make_member(roles=[])
        member.add_roles = AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no"))
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(PermissionError):
            await service.grant(member, "3d", "coordinator@example.com")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.upsert", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_rolls_back_role_on_db_failure(
        self, mock_session_local, mock_get, mock_upsert
    ):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None
        mock_upsert.side_effect = RuntimeError("db exploded")

        role = _make_role()
        member = _make_member(roles=[])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(RuntimeError, match="db exploded"):
            await service.grant(member, "3d", "coordinator@example.com")

        member.add_roles.assert_awaited_once()
        member.remove_roles.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.upsert", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_grant_announce_false_skips_announcement(
        self, mock_session_local, mock_get, mock_upsert
    ):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None

        role = _make_role()
        member = _make_member(roles=[])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.grant(member, "3d", "coordinator@example.com", announce=False)

        assert result.event == TempDriverEvent.GRANTED
        service.announce.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    async def test_grant_propagates_parse_error(self, mock_get):
        role = _make_role()
        member = _make_member(roles=[])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(ValueError, match="Couldn't understand duration"):
            await service.grant(member, "not-a-duration", "coordinator@example.com")


class TestRevoke:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_revoke_removes_role_and_row(self, mock_session_local, mock_get, mock_delete):
        _mock_session_local(mock_session_local)
        existing = _make_grant_row()
        mock_get.return_value = existing
        mock_delete.return_value = True

        role = _make_role()
        member = _make_member(user_id=111, roles=[role])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.revoke("111", "coordinator@example.com")

        assert result.event == TempDriverEvent.REVOKED
        member.remove_roles.assert_awaited_once()
        mock_delete.assert_awaited_once()
        service.announce.assert_awaited_once_with(result.announcement)

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_revoke_skips_remove_roles_if_role_already_gone(
        self, mock_session_local, mock_get, mock_delete
    ):
        _mock_session_local(mock_session_local)
        existing = _make_grant_row()
        mock_get.return_value = existing

        role = _make_role()
        member = _make_member(user_id=111, roles=[])  # role already removed
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        await service.revoke("111", "coordinator@example.com")

        member.remove_roles.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    async def test_revoke_no_grant_raises(self, mock_get):
        mock_get.return_value = None

        member = _make_member(user_id=111, name="alice")
        guild = _make_guild(member=member)
        service = TempDriverService(_make_bot(guild))

        with pytest.raises(ValueError, match="isn't a temporary driver"):
            await service.revoke("111", "coordinator@example.com")

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    async def test_revoke_announce_false_skips_announcement(self, mock_get):
        with (
            patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock),
            patch(f"{MODULE}.AsyncSessionLocal") as mock_session_local,
        ):
            _mock_session_local(mock_session_local)
            mock_get.return_value = _make_grant_row()

            role = _make_role()
            member = _make_member(user_id=111, roles=[role])
            guild = _make_guild(member=member, role=role)
            service = TempDriverService(_make_bot(guild))
            service.announce = AsyncMock()

            await service.revoke("111", "coordinator@example.com", announce=False)

            service.announce.assert_not_called()


class TestAddPermanentDriver:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverService.clear_grant", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_converts_existing_temp_grant(
        self, mock_session_local, mock_get, mock_clear_grant
    ):
        _mock_session_local(mock_session_local)
        mock_get.return_value = _make_grant_row()

        member = _make_member(user_id=111, name="alice", display_name="Alice")
        guild = _make_guild(member_named=member)
        service = TempDriverService(_make_bot(guild))

        result = await service.add_permanent_driver("alice")

        mock_clear_grant.assert_awaited_once_with("111")
        assert result == {
            "discord_user_id": "111",
            "discord_username": "alice",
            "display_name": "Alice",
        }

    @pytest.mark.asyncio
    @patch(f"{MODULE}.RoleManagementService.add_member", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_delegates_when_no_existing_grant(
        self, mock_session_local, mock_get, mock_add_member
    ):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None
        mock_add_member.return_value = {
            "discord_user_id": "111",
            "discord_username": "alice",
            "display_name": "Alice",
        }

        member = _make_member(user_id=111, name="alice", display_name="Alice")
        guild = _make_guild(member_named=member)
        service = TempDriverService(_make_bot(guild))

        result = await service.add_permanent_driver("alice")

        mock_add_member.assert_awaited_once_with("alice", guild, RoleIds.DRIVER)
        assert result["discord_user_id"] == "111"


class TestRemoveDriver:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_removes_via_revoke_when_temp(self, mock_session_local, mock_get, mock_delete):
        _mock_session_local(mock_session_local)
        mock_get.return_value = _make_grant_row()

        role = _make_role()
        member = _make_member(user_id=111, roles=[role])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.remove_driver("111", "coordinator@example.com")

        member.remove_roles.assert_awaited_once()
        service.announce.assert_awaited_once()
        assert result["discord_user_id"] == "111"

    @pytest.mark.asyncio
    @patch(f"{MODULE}.RoleManagementService.remove_member", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.get", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_delegates_when_not_temp(self, mock_session_local, mock_get, mock_remove_member):
        _mock_session_local(mock_session_local)
        mock_get.return_value = None
        mock_remove_member.return_value = {
            "discord_user_id": "111",
            "discord_username": "alice",
            "display_name": "Alice",
        }

        guild = _make_guild()
        service = TempDriverService(_make_bot(guild))

        result = await service.remove_driver("111", "coordinator@example.com")

        mock_remove_member.assert_awaited_once_with("111", guild, RoleIds.DRIVER)
        assert result["discord_user_id"] == "111"


class TestExpireDue:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_expired", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_no_rows_returns_zero(self, mock_session_local, mock_list_expired):
        _mock_session_local(mock_session_local)
        mock_list_expired.return_value = []

        guild = _make_guild()
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.expire_due()

        assert result == 0
        service.announce.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_expired", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_removes_role_and_announces(
        self, mock_session_local, mock_list_expired, mock_delete
    ):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111")
        mock_list_expired.return_value = [row]

        role = _make_role()
        member = _make_member(user_id=111, roles=[role])
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.expire_due()

        assert result == 1
        member.remove_roles.assert_awaited_once()
        mock_delete.assert_awaited_once_with(mock_session_local.return_value, "111")
        service.announce.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_expired", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_member_left_guild_deletes_without_announce(
        self, mock_session_local, mock_list_expired, mock_delete
    ):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111")
        mock_list_expired.return_value = [row]

        role = _make_role()
        guild = _make_guild(member=None, role=role)  # member left
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.expire_due()

        assert result == 1
        service.announce.assert_not_called()
        mock_delete.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_expired", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_role_already_removed_deletes_without_announce(
        self, mock_session_local, mock_list_expired, mock_delete
    ):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111")
        mock_list_expired.return_value = [row]

        role = _make_role()
        member = _make_member(user_id=111, roles=[])  # role already gone
        guild = _make_guild(member=member, role=role)
        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.expire_due()

        assert result == 1
        member.remove_roles.assert_not_called()
        service.announce.assert_not_called()

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_error_to_discord", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_expired", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_per_row_failure_does_not_block_other_rows(
        self, mock_session_local, mock_list_expired, mock_delete, mock_send_error
    ):
        _mock_session_local(mock_session_local)
        row1 = _make_grant_row(discord_user_id="111")
        row2 = _make_grant_row(discord_user_id="222")
        mock_list_expired.return_value = [row1, row2]

        role = _make_role()
        member1 = _make_member(user_id=111, roles=[role])
        member1.remove_roles = AsyncMock(side_effect=RuntimeError("discord is down"))
        member2 = _make_member(user_id=222, roles=[role])

        guild = MagicMock(spec=discord.Guild)
        guild.get_role.return_value = role

        def get_member(uid):
            return {111: member1, 222: member2}.get(uid)

        guild.get_member.side_effect = get_member

        service = TempDriverService(_make_bot(guild))
        service.announce = AsyncMock()

        result = await service.expire_due()

        # Only row2 was successfully processed; row1's failure is isolated.
        assert result == 1
        mock_send_error.assert_awaited_once()
        member2.remove_roles.assert_awaited_once()


class TestClearGrant:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.delete", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_deletes_and_commits(self, mock_session_local, mock_delete):
        session = _mock_session_local(mock_session_local)
        mock_delete.return_value = True

        result = await TempDriverService.clear_grant("111")

        assert result is True
        session.commit.assert_awaited_once()


class TestListGrants:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_bot")
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_all", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_uses_display_name_when_bot_available(
        self, mock_session_local, mock_list_all, mock_get_bot
    ):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111")
        mock_list_all.return_value = [row]

        member = _make_member(user_id=111, display_name="Alice In Guild")
        guild = _make_guild(member=member)
        mock_get_bot.return_value = _make_bot(guild)

        result = await TempDriverService.list_grants()

        assert result[0].display_name == "Alice In Guild"

    @pytest.mark.asyncio
    @patch(f"{MODULE}.get_bot")
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_all", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_falls_back_to_username_when_bot_unavailable(
        self, mock_session_local, mock_list_all, mock_get_bot
    ):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111")
        mock_list_all.return_value = [row]
        mock_get_bot.return_value = None

        result = await TempDriverService.list_grants()

        assert result[0].display_name == "alice"


class TestGetExpiryMap:
    @pytest.mark.asyncio
    @patch(f"{MODULE}.TempDriverGrantsRepository.list_all", new_callable=AsyncMock)
    @patch(f"{MODULE}.AsyncSessionLocal")
    async def test_returns_map_of_aware_utc_datetimes(self, mock_session_local, mock_list_all):
        _mock_session_local(mock_session_local)
        row = _make_grant_row(discord_user_id="111", expires_at=datetime(2026, 1, 1))
        mock_list_all.return_value = [row]

        result = await TempDriverService.get_expiry_map()

        assert result["111"].tzinfo is not None


class TestAnnounce:
    @pytest.mark.asyncio
    async def test_channel_none_logs_warning_and_returns(self):
        bot = MagicMock()
        bot.get_channel.return_value = None
        service = TempDriverService(bot)

        await service.announce("hello")  # should not raise

    @pytest.mark.asyncio
    async def test_sends_with_no_pings(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        bot = MagicMock()
        bot.get_channel.return_value = channel
        service = TempDriverService(bot)

        await service.announce("hello")

        channel.send.assert_awaited_once()
        args, kwargs = channel.send.call_args
        assert args == ("hello",)
        mentions = kwargs["allowed_mentions"]
        assert (mentions.everyone, mentions.users, mentions.roles) == (False, False, False)

    @pytest.mark.asyncio
    @patch(f"{MODULE}.send_error_to_discord", new_callable=AsyncMock)
    async def test_send_failure_is_caught_and_reported(self, mock_send_error):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock(side_effect=RuntimeError("discord down"))
        bot = MagicMock()
        bot.get_channel.return_value = channel
        service = TempDriverService(bot)

        await service.announce("hello")  # should not raise

        mock_send_error.assert_awaited_once()


class TestResolvesChannelWithAppEnv:
    @pytest.mark.asyncio
    async def test_uses_resolved_channel_id(self, monkeypatch):
        from shared.core.enums import ChannelIds

        monkeypatch.setenv("APP_ENV", "local")
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        bot = MagicMock()
        bot.get_channel.return_value = channel
        service = TempDriverService(bot)

        await service.announce("hello")

        bot.get_channel.assert_called_once_with(int(ChannelIds.BOT_STUFF__BOTS))
