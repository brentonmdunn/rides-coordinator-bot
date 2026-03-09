"""Unit tests for AdminService.add_users_to_channel."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.services.admin_service import AdminService


@pytest.fixture
def guild():
    return MagicMock(spec=discord.Guild)


@pytest.fixture
def channel():
    ch = AsyncMock(spec=discord.TextChannel)
    ch.name = "test-channel"
    return ch


@pytest.mark.asyncio
async def test_add_users_all_successful(guild, channel):
    alice = MagicMock(spec=discord.Member)
    bob = MagicMock(spec=discord.Member)

    guild.get_member_named.side_effect = lambda name: {"alice": alice, "bob": bob}.get(name)

    success_count, failed_users = await AdminService.add_users_to_channel(
        "alice bob", channel, guild
    )

    assert success_count == 2
    assert failed_users == []
    assert channel.set_permissions.call_count == 2


@pytest.mark.asyncio
async def test_add_users_partial_failure(guild, channel):
    alice = MagicMock(spec=discord.Member)

    guild.get_member_named.side_effect = lambda name: {"alice": alice}.get(name)

    success_count, failed_users = await AdminService.add_users_to_channel(
        "alice unknown_user", channel, guild
    )

    assert success_count == 1
    assert len(failed_users) == 1
    assert "unknown_user" in failed_users


@pytest.mark.asyncio
async def test_add_users_all_not_found(guild, channel):
    guild.get_member_named.return_value = None

    success_count, failed_users = await AdminService.add_users_to_channel(
        "ghost1 ghost2", channel, guild
    )

    assert success_count == 0
    assert len(failed_users) == 2
    channel.set_permissions.assert_not_called()


@pytest.mark.asyncio
async def test_add_users_strips_at_symbol(guild, channel):
    alice = MagicMock(spec=discord.Member)

    guild.get_member_named.side_effect = lambda name: {"alice": alice}.get(name)

    success_count, failed_users = await AdminService.add_users_to_channel(
        "@alice", channel, guild
    )

    assert success_count == 1
    assert failed_users == []


@pytest.mark.asyncio
async def test_add_users_forbidden_error(guild, channel):
    alice = MagicMock(spec=discord.Member)
    guild.get_member_named.return_value = alice

    channel.set_permissions.side_effect = discord.Forbidden(
        MagicMock(status=403), "Missing Permissions"
    )

    success_count, failed_users = await AdminService.add_users_to_channel(
        "alice", channel, guild
    )

    assert success_count == 0
    assert len(failed_users) == 1
    assert "missing permissions" in failed_users[0].lower()


@pytest.mark.asyncio
async def test_add_users_http_error(guild, channel):
    alice = MagicMock(spec=discord.Member)
    guild.get_member_named.return_value = alice

    channel.set_permissions.side_effect = discord.HTTPException(
        MagicMock(status=500), "Server Error"
    )

    success_count, failed_users = await AdminService.add_users_to_channel(
        "alice", channel, guild
    )

    assert success_count == 0
    assert len(failed_users) == 1
    assert "HTTP Error" in failed_users[0]


@pytest.mark.asyncio
async def test_add_users_sets_correct_permissions(guild, channel):
    alice = MagicMock(spec=discord.Member)
    guild.get_member_named.return_value = alice

    await AdminService.add_users_to_channel("alice", channel, guild)

    channel.set_permissions.assert_called_once()
    _, kwargs = channel.set_permissions.call_args
    overwrite = kwargs["overwrite"]

    assert overwrite.view_channel is True
    assert overwrite.read_messages is True
    assert overwrite.send_messages is True
    assert overwrite.read_message_history is True
