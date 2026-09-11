"""Cog for the whois command."""

import discord
from discord.ext import commands

from ridebot.services.whois_service import WhoisService
from shared.core.logger import log_cmd
from shared.utils.checks import bot_enabled


class Whois(commands.Cog):
    """Cog for looking up user information."""

    def __init__(self, bot: commands.Bot):
        """Initialize the WhoIs cog."""
        self.bot = bot

    @discord.app_commands.command(
        name="whois",
        description="List name and Discord username of potential matches",
    )
    @bot_enabled
    @log_cmd
    async def whois(self, interaction: discord.Interaction, name: str) -> None:
        """
        Fetch and parse names from CSV.

        Args:
            interaction: The Discord interaction.
            name: The name to search for.
        """
        res = await WhoisService.get_whois_data(name)
        message = res if res is not None else "No matches found."
        await interaction.response.send_message(message)


async def setup(bot: commands.Bot):
    """Sets up the Whois cog."""
    await bot.add_cog(Whois(bot))
