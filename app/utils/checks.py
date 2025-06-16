# utils/checks.py
import discord
from discord import app_commands


def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        # Ensure this is used in a guild (not a DM)
        if not interaction.guild or not interaction.user:
            return False

        member = interaction.user

        # Check for Administrator permission
        if isinstance(member, discord.Member):
            return member.guild_permissions.administrator
        return False

    return app_commands.check(predicate)
