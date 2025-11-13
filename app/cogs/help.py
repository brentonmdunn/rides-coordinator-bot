import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.services.help_service import HelpService
from app.utils.checks import feature_flag_enabled


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="List all slash commands with their parameters",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def help(self, interaction: discord.Interaction):
        """Show a list of all available commands."""
        embed = HelpService.build_help_embed(self.bot)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
