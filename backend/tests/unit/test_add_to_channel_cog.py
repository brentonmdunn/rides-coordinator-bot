"""Unit tests for the /add-to-channel cog command."""

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


@pytest.mark.asyncio
async def test_add_to_channel_success(admin_cog):
    interaction = AsyncMock()
    interaction.data = {"name": "add-to-channel", "options": []}
    interaction.user = MagicMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.channel.mention = "#test-channel"
    interaction.guild = MagicMock(spec=discord.Guild)

    with patch(
        "bot.cogs.admin.AdminService.add_users_to_channel", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = (3, [])

        await admin_cog.add_to_channel.callback(
            admin_cog, interaction, "alice bob charlie"
        )

        mock_service.assert_called_once_with(
            "alice bob charlie", interaction.channel, interaction.guild
        )

        interaction.followup.send.assert_called_once()
        _, kwargs = interaction.followup.send.call_args
        embed = kwargs.get("embed")
        assert embed is not None
        assert "3 users" in embed.description


@pytest.mark.asyncio
async def test_add_to_channel_with_failures(admin_cog):
    interaction = AsyncMock()
    interaction.data = {"name": "add-to-channel", "options": []}
    interaction.user = MagicMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.channel.mention = "#test-channel"
    interaction.guild = MagicMock(spec=discord.Guild)

    with patch(
        "bot.cogs.admin.AdminService.add_users_to_channel", new_callable=AsyncMock
    ) as mock_service:
        mock_service.return_value = (1, ["unknown_user"])

        await admin_cog.add_to_channel.callback(
            admin_cog, interaction, "alice unknown_user"
        )

        interaction.followup.send.assert_called_once()
        _, kwargs = interaction.followup.send.call_args
        embed = kwargs.get("embed")
        assert embed is not None
        assert len(embed.fields) == 1
        assert "unknown_user" in embed.fields[0].value


@pytest.mark.asyncio
async def test_add_to_channel_service_exception(admin_cog):
    interaction = AsyncMock()
    interaction.data = {"name": "add-to-channel", "options": []}
    interaction.user = MagicMock()
    interaction.channel = MagicMock(spec=discord.TextChannel)
    interaction.guild = MagicMock(spec=discord.Guild)

    with patch(
        "bot.cogs.admin.AdminService.add_users_to_channel", new_callable=AsyncMock
    ) as mock_service, patch("bot.cogs.admin.send_error_to_discord", new_callable=AsyncMock):
        mock_service.side_effect = Exception("Unexpected")

        await admin_cog.add_to_channel.callback(
            admin_cog, interaction, "alice"
        )

        interaction.followup.send.assert_called_once_with(
            "An unexpected error occurred. Please try again later."
        )
