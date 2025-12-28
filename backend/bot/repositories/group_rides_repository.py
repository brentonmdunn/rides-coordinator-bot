"""Repository for group rides data access."""

import discord
from discord.ext import commands


class GroupRidesRepository:
    """Handles data access for group rides."""

    def __init__(self, bot: commands.Bot):
        """Initialize the GroupRidesRepository."""

        self.bot = bot

    async def fetch_message(self, channel_id: int, message_id: int) -> discord.Message:
        """Fetches a message from a channel.

        Args:
            channel_id: The ID of the channel.
            message_id: The ID of the message.

        Returns:
            The Discord Message object if found, otherwise None.
        """
        channel = self.bot.get_channel(channel_id)
        if not channel:
            # Try fetching if not in cache, though get_channel usually gets from cache
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.NotFound:
                return None

        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            return None
