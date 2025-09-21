import discord
from discord.ext import commands
from sqlalchemy import func, or_, select

from app.core.database import AsyncSessionLocal
from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.core.models import Locations as LocationsModel
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

        async with AsyncSessionLocal() as session:
            stmt = select(LocationsModel.name, LocationsModel.discord_username).where(
                or_(
                    func.lower(LocationsModel.name).contains(name.lower()),
                    func.lower(LocationsModel.discord_username).contains(name.lower()),
                )
            )
            result = await session.execute(stmt)
            possible_people = result.all()

        if not possible_people:
            await interaction.response.send_message("No matches found.")
            return

        message: list[str] = []
        for person in possible_people:
            message.append(f"**Name:** {person.name}\n**Discord:** {person.discord_username}")

        await interaction.response.send_message("\n---\n".join(message))


async def setup(bot: commands.Bot):
    await bot.add_cog(Whois(bot))
