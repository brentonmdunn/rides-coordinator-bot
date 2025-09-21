import discord
from discord import app_commands
from discord.abc import Messageable
from discord.ext import commands

from app.core.enums import ChannelIds, FeatureFlagNames
from app.core.logger import logger
from app.jobs.ask_rides import _make_sunday_msg
from app.utils.checks import feature_flag_enabled


class TestCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="test",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def test(self, interaction: discord.Interaction):
        channel: Messageable | None = self.bot.get_channel(
            ChannelIds.BOT_STUFF__BOTS,
        )
        if not channel:
            logger.info("Error channel not found")
            return
        message: str | None = _make_sunday_msg()
        if message is None:
            logger.info("here")
            return
        sent_message = await channel.send(
            message,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        await interaction.response.send_message("complete")

        reactions = ["🍔", "🏠", "➡️", "⬅️", "✳️"]
        for emoji in reactions:
            await sent_message.add_reaction(emoji)


async def setup(bot: commands.Bot):
    await bot.add_cog(TestCog(bot))
