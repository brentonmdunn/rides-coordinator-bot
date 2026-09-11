"""Service for admin-related operations."""

import logging

import discord

from bot.utils.parsing import parse_discord_username

logger = logging.getLogger(__name__)


class AdminService:
    """Service for handling admin tasks."""

    @staticmethod
    async def assign_roles_from_csv(
        role: discord.Role, discord_usernames: str, guild: discord.Guild
    ) -> tuple[int, list[str]]:
        """
        Assigns a role to users listed in a CSV column.

        Args:
            role: The role to assign.
            discord_usernames: The Discord usernames to assign the role to.
            guild: The guild to find members in.

        Returns:
            A tuple containing the count of successful assignments and a list of failed usernames.

        Raises:
            Exception: If CSV retrieval fails or other errors occur.
        """
        success_count = 0
        failed_users = []

        logger.info(f"assign_roles_from_csv: assigning role={role.name} to users from CSV input")

        for username in discord_usernames.split():
            # Clean username (remove @ if present)
            username = parse_discord_username(username)

            # Find user
            member = guild.get_member_named(username)
            if not member:
                failed_users.append(username)
                continue

            # Assign role
            try:
                if role not in member.roles:
                    await member.add_roles(role)
                    success_count += 1
            except discord.Forbidden:
                raise Exception("I do not have permission to assign this role.")  # noqa: B904
            except discord.HTTPException as e:
                failed_users.append(f"{username} (HTTP Error: {e})")

        logger.info(
            f"assign_roles_from_csv: completed - {success_count} assigned, "
            f"{len(failed_users)} failed"
        )
        return success_count, failed_users

    @staticmethod
    async def add_users_to_channel(
        discord_usernames: str,
        channel: discord.TextChannel,
        guild: discord.Guild,
    ) -> tuple[int, list[str]]:
        """
        Grants read/write permissions in a channel to the specified users.

        Args:
            discord_usernames: Space-separated Discord usernames.
            channel: The channel to grant access to.
            guild: The guild to find members in.

        Returns:
            A tuple containing the count of successful grants and a list of failed usernames.
        """
        success_count = 0
        failed_users = []

        logger.info(
            f"add_users_to_channel: granting access in channel={channel.name} to users from input"
        )

        for username in discord_usernames.split():
            username = parse_discord_username(username)

            member = guild.get_member_named(username)
            if not member:
                failed_users.append(username)
                continue

            try:
                overwrites = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                )
                await channel.set_permissions(member, overwrite=overwrites)
                success_count += 1
            except discord.Forbidden:
                failed_users.append(f"{username} (missing permissions)")
            except discord.HTTPException as e:
                failed_users.append(f"{username} (HTTP Error: {e})")

        logger.info(
            f"add_users_to_channel: completed - {success_count} granted, {len(failed_users)} failed"
        )
        return success_count, failed_users
