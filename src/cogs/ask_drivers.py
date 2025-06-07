"""
cogs/ask_drivers.py
"""

import discord
from discord.ext import commands

from enums import ChannelIds, RoleIds
from utils.format_message import ping_role_with_message


class AskDrivers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @discord.app_commands.command(
        name="ask-drivers", description="Pings drivers to see who is available."
    )
    async def ask_drivers(self, interaction: discord.Interaction, message: str) -> None:
        """Pings the driver role with a custom message."""
        # Only allow usage in the DRIVER_CHAT_WOOOOO channel
        if interaction.channel_id != ChannelIds.SERVING__DRIVER_CHAT_WOOOOO:
            await interaction.response.send_message(
                f"`/ask-drivers` can only be used in <#{ChannelIds.SERVING__DRIVER_CHAT_WOOOOO}>",
                ephemeral=True,
            )
            return

        message_to_send = ping_role_with_message(RoleIds.DRIVER, message)

        # Send the message and allow role mentions
        await interaction.response.send_message(
            message_to_send, allowed_mentions=discord.AllowedMentions(roles=True)
        )

        # Fetch the original response
        sent_message = await interaction.original_response()

        reactions = ["👍", "❌", "➡️", "⬅️", "💩"]
        for emoji in reactions:
            await sent_message.add_reaction(emoji)


async def setup(bot: commands.Bot):
    await bot.add_cog(AskDrivers(bot))
