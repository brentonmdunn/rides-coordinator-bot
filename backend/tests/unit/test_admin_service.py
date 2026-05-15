"""Unit tests for AdminService."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.services.admin_service import AdminService


def _make_member(username: str, roles: list | None = None) -> MagicMock:
    member = MagicMock(spec=discord.Member)
    member.roles = roles or []
    member.add_roles = AsyncMock()
    return member


def _make_guild(members: dict[str, MagicMock]) -> MagicMock:
    guild = MagicMock(spec=discord.Guild)
    guild.get_member_named.side_effect = lambda name: members.get(name)
    return guild


def _make_role(name: str = "TestRole") -> MagicMock:
    role = MagicMock(spec=discord.Role)
    role.name = name
    role.mention = f"@{name}"
    return role


@pytest.mark.asyncio
async def test_assign_roles_success():
    alice = _make_member("alice")
    bob = _make_member("bob")
    guild = _make_guild({"alice": alice, "bob": bob})
    role = _make_role()

    count, failed = await AdminService.assign_roles_from_csv(role, "alice bob", guild)

    assert count == 2
    assert failed == []
    alice.add_roles.assert_awaited_once_with(role)
    bob.add_roles.assert_awaited_once_with(role)


@pytest.mark.asyncio
async def test_assign_roles_member_not_found():
    alice = _make_member("alice")
    guild = _make_guild({"alice": alice})
    role = _make_role()

    count, failed = await AdminService.assign_roles_from_csv(role, "alice charlie", guild)

    assert count == 1
    assert "charlie" in failed


@pytest.mark.asyncio
async def test_assign_roles_strips_at_symbol():
    alice = _make_member("alice")
    guild = _make_guild({"alice": alice})
    role = _make_role()

    count, failed = await AdminService.assign_roles_from_csv(role, "@alice", guild)

    assert count == 1
    assert failed == []


@pytest.mark.asyncio
async def test_assign_roles_skips_already_assigned():
    role = _make_role()
    alice = _make_member("alice", roles=[role])
    guild = _make_guild({"alice": alice})

    count, _failed = await AdminService.assign_roles_from_csv(role, "alice", guild)

    assert count == 0
    alice.add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_roles_forbidden_raises():
    role = _make_role()
    alice = _make_member("alice")
    alice.add_roles.side_effect = discord.Forbidden(MagicMock(), "no perms")
    guild = _make_guild({"alice": alice})

    with pytest.raises(Exception, match="permission"):
        await AdminService.assign_roles_from_csv(role, "alice", guild)


@pytest.mark.asyncio
async def test_assign_roles_http_error_adds_to_failed():
    role = _make_role()
    alice = _make_member("alice")
    alice.add_roles.side_effect = discord.HTTPException(MagicMock(), "server error")
    guild = _make_guild({"alice": alice})

    count, failed = await AdminService.assign_roles_from_csv(role, "alice", guild)

    assert count == 0
    assert any("alice" in f for f in failed)


@pytest.mark.asyncio
async def test_add_users_to_channel_success():
    alice = _make_member("alice")
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "general"
    channel.set_permissions = AsyncMock()
    guild = _make_guild({"alice": alice})

    count, failed = await AdminService.add_users_to_channel("alice", channel, guild)

    assert count == 1
    assert failed == []
    channel.set_permissions.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_users_to_channel_not_found():
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "general"
    guild = _make_guild({})

    count, failed = await AdminService.add_users_to_channel("ghost", channel, guild)

    assert count == 0
    assert "ghost" in failed


@pytest.mark.asyncio
async def test_add_users_to_channel_forbidden():
    alice = _make_member("alice")
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "general"
    channel.set_permissions = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "no perms"))
    guild = _make_guild({"alice": alice})

    count, failed = await AdminService.add_users_to_channel("alice", channel, guild)

    assert count == 0
    assert any("alice" in f for f in failed)


@pytest.mark.asyncio
async def test_add_users_to_channel_http_error():
    alice = _make_member("alice")
    channel = MagicMock(spec=discord.TextChannel)
    channel.name = "general"
    channel.set_permissions = AsyncMock(
        side_effect=discord.HTTPException(MagicMock(), "server error")
    )
    guild = _make_guild({"alice": alice})

    count, failed = await AdminService.add_users_to_channel("alice", channel, guild)

    assert count == 0
    assert any("alice" in f for f in failed)
