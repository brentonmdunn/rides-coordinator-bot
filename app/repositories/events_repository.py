# app/repositories/events_repository.py

import discord
from discord.ext import commands


class EventsRepository:
    """
    Handles all data access related to Discord objects like roles,
    messages, and members.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_guild(self, guild_id: int) -> discord.Guild | None:
        """Fetches a guild by its ID from the bot's cache."""
        return self.bot.get_guild(guild_id)

    def get_text_channel(self, guild: discord.Guild, channel_id: int) -> discord.TextChannel | None:
        """Fetches a text channel by its ID from a guild's cache."""
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def fetch_message(
        self, channel: discord.TextChannel, message_id: int
    ) -> discord.Message | None:
        """Fetches a specific message from a channel, or None if not found."""
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            return None

    def get_role_by_name(self, guild: discord.Guild, role_name: str) -> discord.Role | None:
        """Finds a role in a guild by its exact name."""
        return discord.utils.get(guild.roles, name=role_name)

    async def get_reacting_members(
        self, message: discord.Message, guild: discord.Guild
    ) -> set[discord.Member]:
        """
        Gathers a unique set of valid members who reacted to a message.
        """
        members = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if user.bot:
                    continue

                # Use guild.get_member for a fast cache lookup
                member = guild.get_member(user.id)
                if member:
                    members.add(member)
        return members

    async def add_role_to_member(
        self, member: discord.Member, role: discord.Role, reason: str
    ) -> bool:
        """
        Adds a role to a member.
        Returns True on success, False on failure (e.g., permissions error).
        """
        try:
            await member.add_roles(role, reason=reason)
            return True
        except discord.Forbidden:
            print(f"Failed to add role {role.name} to {member.name}: Forbidden.")
            return False
        except discord.HTTPException as e:
            print(f"Failed to add role {role.name} to {member.name}: {e}")
            return False
