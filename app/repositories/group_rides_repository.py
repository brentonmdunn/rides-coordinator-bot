import discord
from discord.ext import commands


class GroupRidesRepository:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_message(self, channel_id: int, message_id: int) -> discord.Message:
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
