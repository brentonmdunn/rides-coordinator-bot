# from unittest.mock import AsyncMock, MagicMock, patch

# import discord
# import pytest

# from bot.cogs.admin import Admin


# @pytest.fixture
# def mock_bot():
#     return MagicMock()


# @pytest.fixture
# def admin_cog(mock_bot):
#     return Admin(mock_bot)


# @pytest.mark.asyncio
# async def test_give_role_success(admin_cog):
#     interaction = AsyncMock()
#     interaction.data = {"name": "give-role", "options": []}
#     interaction.user = MagicMock()
#     interaction.channel = MagicMock()
#     interaction.guild = MagicMock()

#     role = MagicMock(spec=discord.Role)
#     role.mention = "@Role"

#     with patch(
#         "bot.services.admin_service.AdminService.assign_roles_from_csv", new_callable=AsyncMock
#     ) as mock_service:
#         mock_service.return_value = (2, [])

#         await admin_cog.give_role.callback(
#             admin_cog, interaction, role, "B", "http://example.com/file.csv"
#         )

#         mock_service.assert_called_once_with(
#             role, "B", "http://example.com/file.csv", interaction.guild
#         )

#         # Verify success message
#         interaction.followup.send.assert_called()
#         _, kwargs = interaction.followup.send.call_args
#         embed = kwargs.get("embed")
#         assert embed is not None
#         assert "Assigned @Role to 2 users" in embed.description


# @pytest.mark.asyncio
# async def test_give_role_service_error(admin_cog):
#     interaction = AsyncMock()
#     interaction.data = {"name": "give-role", "options": []}
#     interaction.user = MagicMock()
#     interaction.channel = MagicMock()
#     role = MagicMock(spec=discord.Role)

#     with patch(
#         "bot.services.admin_service.AdminService.assign_roles_from_csv", new_callable=AsyncMock
#     ) as mock_service:
#         mock_service.side_effect = Exception("Service Error")

#         await admin_cog.give_role.callback(
#             admin_cog, interaction, role, "A", "http://example.com/file.csv"
#         )

#         interaction.followup.send.assert_called_with("An error occurred: Service Error")
