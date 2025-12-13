# from unittest.mock import MagicMock, patch

# import discord
# import pytest

# from app.services.admin_service import AdminService


# @pytest.mark.asyncio
# async def test_assign_roles_from_csv_success():
#     guild = MagicMock(spec=discord.Guild)
#     role = MagicMock(spec=discord.Role)

#     # Mock members
#     alice = MagicMock(spec=discord.Member)
#     alice.roles = []
#     bob = MagicMock(spec=discord.Member)
#     bob.roles = []

#     guild.get_member_named.side_effect = lambda name: {"alice": alice, "bob": bob}.get(name)

#     csv_content = "Name,Discord Username\nAlice,alice\nBob,bob"

#     with patch("requests.get") as mock_get:
#         mock_get.return_value.status_code = 200
#         mock_get.return_value.content = csv_content.encode("utf-8")

#         success_count, failed_users = await AdminService.assign_roles_from_csv(
#             role, "B", "http://example.com/file.csv", guild
#         )

#         assert success_count == 2
#         assert len(failed_users) == 0
#         alice.add_roles.assert_called_with(role)
#         bob.add_roles.assert_called_with(role)


# @pytest.mark.asyncio
# async def test_assign_roles_from_csv_partial_failure():
#     guild = MagicMock(spec=discord.Guild)
#     role = MagicMock(spec=discord.Role)

#     # Mock members
#     alice = MagicMock(spec=discord.Member)
#     alice.roles = []

#     # Charlie not found
#     guild.get_member_named.side_effect = lambda name: {"alice": alice}.get(name)

#     csv_content = "Name,Discord Username\nAlice,alice\nCharlie,charlie"

#     with patch("requests.get") as mock_get:
#         mock_get.return_value.status_code = 200
#         mock_get.return_value.content = csv_content.encode("utf-8")

#         success_count, failed_users = await AdminService.assign_roles_from_csv(
#             role, "B", "http://example.com/file.csv", guild
#         )

#         assert success_count == 1
#         assert len(failed_users) == 1
#         assert "charlie" in failed_users
#         alice.add_roles.assert_called_with(role)


# @pytest.mark.asyncio
# async def test_assign_roles_from_csv_fetch_error():
#     guild = MagicMock(spec=discord.Guild)
#     role = MagicMock(spec=discord.Role)

#     with patch("requests.get") as mock_get:
#         mock_get.return_value.status_code = 404

#         with pytest.raises(Exception) as excinfo:
#             await AdminService.assign_roles_from_csv(
#                 role, "B", "http://example.com/file.csv", guild
#             )

#         assert "Failed to retrieve CSV data" in str(excinfo.value)
