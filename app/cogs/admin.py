"""Admin cog for administrative tasks."""

import discord
from discord import app_commands
from discord.ext import commands

from app.core.logger import log_cmd
from app.services.admin_service import AdminService


class Admin(commands.Cog):
    """Cog for administrative commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="give-role", description="Assign a role to users from a CSV file.")
    @app_commands.describe(
        role="The role to assign.",
        column_letter="The column letter containing Discord usernames (e.g., 'A', 'AB').",
        csv_url="The URL of the CSV file.",
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    @log_cmd
    async def give_role(
        self, interaction: discord.Interaction, role: discord.Role, column_letter: str, csv_url: str
    ) -> None:
        """Assigns a role to users listed in a CSV column.

        Args:
            interaction: The Discord interaction.
            role: The role to assign.
            column_letter: The column letter containing usernames.
            csv_url: The URL of the CSV file.
        """
        await interaction.response.defer()

        try:
            success_count, failed_users = await AdminService.assign_roles_from_csv(
                role, column_letter, csv_url, interaction.guild
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

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")


async def setup(bot: commands.Bot):
    """Sets up the Admin cog."""
    await bot.add_cog(Admin(bot))
