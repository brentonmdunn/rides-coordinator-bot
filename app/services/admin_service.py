"""Service for admin-related operations."""

import csv
import io

import discord
import requests

from app.utils.parsing import column_letter_to_index, parse_discord_username


class AdminService:
    """Service for handling admin tasks."""

    @staticmethod
    async def assign_roles_from_csv(
        role: discord.Role, column_letter: str, csv_url: str, guild: discord.Guild
    ) -> tuple[int, list[str]]:
        """Assigns a role to users listed in a CSV column.

        Args:
            role: The role to assign.
            column_letter: The column letter containing usernames.
            csv_url: The URL of the CSV file.
            guild: The guild to find members in.

        Returns:
            A tuple containing the count of successful assignments and a list of failed usernames.

        Raises:
            Exception: If CSV retrieval fails or other errors occur.
        """
        response = requests.get(csv_url)
        if response.status_code != 200:
            raise Exception(f"Failed to retrieve CSV data. Status code: {response.status_code}")

        csv_data = response.content.decode("utf-8")
        csv_file = io.StringIO(csv_data)
        reader = csv.reader(csv_file)

        column_index = column_letter_to_index(column_letter)

        success_count = 0
        failed_users = []

        for row in reader:
            if not row:
                continue

            if len(row) <= column_index:
                continue

            username = row[column_index].strip()
            if not username:
                continue

            # Handle potential header or empty cells
            if "discord" in username.lower():
                continue

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
