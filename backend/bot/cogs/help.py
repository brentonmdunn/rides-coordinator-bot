"""Cog for the help command."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.enums import FeatureFlagNames
from bot.core.logger import log_cmd
from bot.services.help_service import HelpService
from bot.utils.checks import feature_flag_enabled


class HelpCog(commands.Cog):
    """Cog for displaying help information."""

    def __init__(self, bot: commands.Bot, help_service: HelpService):
        """Initialize the Help cog."""

        self.bot = bot
        self.help_service = help_service

    @app_commands.command(
        name="help",
        description="List all slash commands with their parameters",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def help(self, interaction: discord.Interaction):
        """Show a list of all available commands.

        Args:
            interaction: The Discord interaction.
        """
        embed = self.help_service.build_help_embed(self.bot)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Sets up the HelpCog."""
    service = HelpService()
    await bot.add_cog(HelpCog(bot, help_service=service))
