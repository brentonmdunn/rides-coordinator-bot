"""Admin cog for administrative tasks."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.api import send_error_to_discord
from bot.core.logger import log_cmd
from bot.services.admin_service import AdminService

logger = logging.getLogger(__name__)


class Admin(commands.Cog):
    """Cog for administrative commands."""

    def __init__(self, bot: commands.Bot):
        """Initialize the Admin cog."""
        self.bot = bot

    @app_commands.command(name="give-role", description="Assign a role to users from a CSV file.")
    @app_commands.describe(
        role="The role to assign.",
        discord_usernames="The Discord usernames to assign the role to.",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    @log_cmd
    async def give_role(
        self, interaction: discord.Interaction, role: discord.Role, discord_usernames: str
    ) -> None:
        """
        Assigns a role to users listed in a CSV column.

        Args:
            interaction: The Discord interaction.
            role: The role to assign.
            discord_usernames: The Discord usernames to assign the role to.
        """
        await interaction.response.defer()

        try:
            success_count, failed_users = await AdminService.assign_roles_from_csv(
                role, discord_usernames, interaction.guild
            )

            embed = discord.Embed(
                title="Role Assignment Complete",
                description=f"Assigned {role.mention} to {success_count} users.",
                color=discord.Color.green(),
            )

            if failed_users:
                # Truncate if too long
                failed_list = ", ".join(failed_users)
                if len(failed_list) > 1000:
                    failed_list = failed_list[:1000] + "..."

                embed.add_field(
                    name=f"Failed to find/assign ({len(failed_users)})",
                    value=failed_list,
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception:
            logger.exception("Unexpected error in give_role")
            await send_error_to_discord("**Unexpected Error** in `/give-role`")
            await interaction.followup.send("An unexpected error occurred. Please try again later.")

    @app_commands.command(
        name="add-to-channel",
        description="Grant users read/write access to the current channel.",
    )
    @app_commands.describe(
        discord_usernames="Space-separated Discord usernames to grant access to.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    @log_cmd
    async def add_to_channel(
        self, interaction: discord.Interaction, discord_usernames: str
    ) -> None:
        """
        Grants read/write channel permissions to the specified users.

        Args:
            interaction: The Discord interaction.
            discord_usernames: Space-separated Discord usernames.
        """
        await interaction.response.defer()

        try:
            success_count, failed_users = await AdminService.add_users_to_channel(
                discord_usernames, interaction.channel, interaction.guild
            )

            embed = discord.Embed(
                title="Channel Access Updated",
                description=(
                    f"Granted read/write access to {success_count} users "
                    f"in {interaction.channel.mention}."
                ),
                color=discord.Color.green(),
            )

            if failed_users:
                failed_list = ", ".join(failed_users)
                if len(failed_list) > 1000:
                    failed_list = failed_list[:1000] + "..."

                embed.add_field(
                    name=f"Failed to find/assign ({len(failed_users)})",
                    value=failed_list,
                    inline=False,
                )

            await interaction.followup.send(embed=embed)

        except Exception:
            logger.exception("Unexpected error in add_to_channel")
            await send_error_to_discord("**Unexpected Error** in `/add-to-channel`")
            await interaction.followup.send("An unexpected error occurred. Please try again later.")


async def setup(bot: commands.Bot):
    """Sets up the Admin cog."""
    await bot.add_cog(Admin(bot))
