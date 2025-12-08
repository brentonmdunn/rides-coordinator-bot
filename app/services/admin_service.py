"""Service for admin-related operations."""


import discord

from app.utils.parsing import parse_discord_username


class AdminService:
    """Service for handling admin tasks."""

    @staticmethod
    async def assign_roles_from_csv(
        role: discord.Role, discord_usernames: str, guild: discord.Guild
    ) -> tuple[int, list[str]]:
        """Assigns a role to users listed in a CSV column.

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

        return success_count, failed_users
