import csv
import os

import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv

from app.utils.parsing import parse_name

load_dotenv()

LSCC_PPL_CSV_URL = os.getenv("LSCC_PPL_CSV_URL")


class Whois(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="whois",
        description="List name and Discord username of potential matches",
    )
    async def whois(self, interaction: discord.Interaction, name: str) -> None:
        """Fetch and parse names from CSV."""
        response = requests.get(LSCC_PPL_CSV_URL)

        if response.status_code != 200:
            await interaction.response.send_message("⚠️ Failed to fetch the CSV data.")
            return

        csv_data = response.content.decode("utf-8")
        csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

        message = ""
        found = False

        for row in csv_reader:
            for _, cell in enumerate(row):
                if name.lower() in cell.lower():
                    saved_name, discord_username = parse_name(cell)
                    found = True
                    if saved_name:
                        message += f"\n**Name:** {saved_name}"
                    if discord_username:
                        message += f"\n**Discord:** {discord_username}"
                    message += "\n---"

        if not found:
            await interaction.response.send_message("No matches found.")
        else:
            await interaction.response.send_message(message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Whois(bot))
