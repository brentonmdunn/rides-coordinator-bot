"""Service for managing Discord Driver role assignments."""

import logging

import discord

from bot.core.enums import RoleIds
from bot.utils.parsing import parse_discord_username

logger = logging.getLogger(__name__)


class DriverManagementService:
    """Service for listing, adding, and removing the Driver Discord role."""

    @staticmethod
    def _driver_role(guild: discord.Guild) -> discord.Role | None:
        return guild.get_role(int(RoleIds.DRIVER))

    @staticmethod
    def get_drivers(guild: discord.Guild) -> list[dict]:
        """Return all guild members who currently have the Driver role."""
        role = DriverManagementService._driver_role(guild)
        if role is None:
            logger.warning("Driver role not found in guild")
            return []
        return [
            {
                "discord_user_id": str(member.id),
                "discord_username": str(member.name),
                "display_name": member.display_name,
            }
            for member in role.members
        ]

    @staticmethod
    async def add_driver(username: str, guild: discord.Guild) -> dict:
        """
        Add the Driver role to a guild member by username.

        Returns:
            dict with member info on success.

        Raises:
            ValueError: If the member is not found or already has the role.
            PermissionError: If the bot lacks permission.
        """
        username = parse_discord_username(username)
        member = guild.get_member_named(username)
        if member is None:
            raise ValueError(f"Member '{username}' not found in server")

        role = DriverManagementService._driver_role(guild)
        if role is None:
            raise ValueError("Driver role not found in server")

        if role in member.roles:
            raise ValueError(f"@{username} already has the Driver role")

        try:
            await member.add_roles(role)
        except discord.Forbidden:
            raise PermissionError("Bot lacks permission to assign roles")  # noqa: B904
        except discord.HTTPException as e:
            raise ValueError(f"Discord error adding role: {e}")  # noqa: B904

        logger.info(f"Driver role added to {member.name} ({member.id})")
        return {
            "discord_user_id": str(member.id),
            "discord_username": str(member.name),
            "display_name": member.display_name,
        }

    @staticmethod
    async def remove_driver(discord_user_id: str, guild: discord.Guild) -> dict:
        """
        Remove the Driver role from a guild member by Discord user ID.

        Returns:
            dict with member info on success.

        Raises:
            ValueError: If the member is not found or doesn't have the role.
            PermissionError: If the bot lacks permission.
        """
        member = guild.get_member(int(discord_user_id))
        if member is None:
            raise ValueError(f"Member with ID {discord_user_id} not found in server")

        role = DriverManagementService._driver_role(guild)
        if role is None:
            raise ValueError("Driver role not found in server")

        if role not in member.roles:
            raise ValueError(f"@{member.name} does not have the Driver role")

        try:
            await member.remove_roles(role)
        except discord.Forbidden:
            raise PermissionError("Bot lacks permission to remove roles")  # noqa: B904
        except discord.HTTPException as e:
            raise ValueError(f"Discord error removing role: {e}")  # noqa: B904

        logger.info(f"Driver role removed from {member.name} ({member.id})")
        return {
            "discord_user_id": str(member.id),
            "discord_username": str(member.name),
            "display_name": member.display_name,
        }

    @staticmethod
    def search_non_drivers(query: str, guild: discord.Guild, limit: int = 10) -> list[dict]:
        """
        Search guild members whose username or display name matches query.
        Only returns members who do NOT already have the Driver role.
        """
        role = DriverManagementService._driver_role(guild)
        driver_ids = {m.id for m in role.members} if role else set()

        query_lower = query.lower()
        results: list[dict] = []
        for member in guild.members:
            if member.id in driver_ids or member.bot:
                continue
            if query_lower in member.name.lower() or query_lower in member.display_name.lower():
                results.append(
                    {
                        "discord_user_id": str(member.id),
                        "discord_username": str(member.name),
                        "display_name": member.display_name,
                    }
                )
                if len(results) >= limit:
                    break
        return results
