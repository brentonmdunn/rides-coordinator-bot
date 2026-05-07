"""Unit tests for the Admin cog."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from bot.cogs.admin import Admin


@pytest.fixture
def mock_bot():
    return MagicMock()


@pytest.fixture
def admin_cog(mock_bot):
    return Admin(mock_bot)


def _make_interaction(command_name: str) -> AsyncMock:
    """Build a minimal Discord interaction mock compatible with @log_cmd."""
    interaction = AsyncMock()
    interaction.data = {"name": command_name, "options": []}
    interaction.user = MagicMock()
    interaction.guild = MagicMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.channel.mention = "#general"
    return interaction


@pytest.mark.asyncio
async def test_give_role_success(admin_cog):
    interaction = _make_interaction("give-role")
    role = MagicMock(spec=discord.Role)
    role.mention = "@Role"

    with patch(
        "bot.cogs.admin.AdminService.assign_roles_from_csv",
        new_callable=AsyncMock,
        return_value=(2, []),
    ):
        await admin_cog.give_role.callback(admin_cog, interaction, role, "alice bob")

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()
    _, kwargs = interaction.followup.send.call_args
    embed = kwargs.get("embed")
    assert embed is not None
    assert "2" in embed.description


@pytest.mark.asyncio
async def test_give_role_with_failures(admin_cog):
    interaction = _make_interaction("give-role")
    role = MagicMock(spec=discord.Role)
    role.mention = "@Role"

    with patch(
        "bot.cogs.admin.AdminService.assign_roles_from_csv",
        new_callable=AsyncMock,
        return_value=(1, ["charlie"]),
    ):
        await admin_cog.give_role.callback(admin_cog, interaction, role, "alice charlie")

    _, kwargs = interaction.followup.send.call_args
    embed = kwargs.get("embed")
    assert embed is not None
    assert any("charlie" in f.value for f in embed.fields)


@pytest.mark.asyncio
async def test_give_role_unexpected_error(admin_cog):
    interaction = _make_interaction("give-role")
    role = MagicMock(spec=discord.Role)

    with (
        patch(
            "bot.cogs.admin.AdminService.assign_roles_from_csv",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch("bot.cogs.admin.send_error_to_discord", new_callable=AsyncMock),
    ):
        await admin_cog.give_role.callback(admin_cog, interaction, role, "alice")

    interaction.followup.send.assert_awaited()
    args = interaction.followup.send.call_args[0]
    assert "unexpected error" in args[0].lower()


@pytest.mark.asyncio
async def test_add_to_channel_success(admin_cog):
    interaction = _make_interaction("add-to-channel")

    with patch(
        "bot.cogs.admin.AdminService.add_users_to_channel",
        new_callable=AsyncMock,
        return_value=(1, []),
    ):
        await admin_cog.add_to_channel.callback(admin_cog, interaction, "alice")

    interaction.followup.send.assert_awaited_once()
    _, kwargs = interaction.followup.send.call_args
    assert kwargs.get("embed") is not None


@pytest.mark.asyncio
async def test_add_to_channel_unexpected_error(admin_cog):
    interaction = _make_interaction("add-to-channel")

    with (
        patch(
            "bot.cogs.admin.AdminService.add_users_to_channel",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch("bot.cogs.admin.send_error_to_discord", new_callable=AsyncMock),
    ):
        await admin_cog.add_to_channel.callback(admin_cog, interaction, "alice")

    interaction.followup.send.assert_awaited()
    args = interaction.followup.send.call_args[0]
    assert "unexpected error" in args[0].lower()
