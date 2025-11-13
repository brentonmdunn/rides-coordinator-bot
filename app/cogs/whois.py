import discord
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.services.whois_service import WhoisService
from app.utils.checks import feature_flag_enabled


class Whois(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="whois",
        description="List name and Discord username of potential matches",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @log_cmd
    async def whois(self, interaction: discord.Interaction, name: str) -> None:
        """Fetch and parse names from CSV."""
        res = await WhoisService.get_whois_data(name)
        message = res if res is not None else "No matches found."
        await interaction.response.send_message(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Whois(bot))
