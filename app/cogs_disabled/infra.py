import discord
from discord.ext import commands

from app.core.database import AsyncSessionLocal
from app.core.enums import FeatureFlagNames
from app.core.models import DiscordUsers
from app.utils.checks import feature_flag_enabled, is_admin


class Infra(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="add-user",
        description="Adds user and Discord username to database",
    )
    @is_admin()
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def add_user(
        self,
        interaction: discord.Interaction,
        discord_username: str,
        first_name: str,
        last_name: str,
    ) -> None:
        async with AsyncSessionLocal() as session:
            new_user = DiscordUsers(
                discord_username=discord_username,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(new_user)
            await session.commit()

        await interaction.response.send_message(
            f"✅ User `@{discord_username}` added to database",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Infra(bot))
