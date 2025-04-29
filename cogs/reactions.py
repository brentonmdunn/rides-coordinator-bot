import discord
from discord.ext import commands

from enums import ChannelIds, DayOfWeek
from utils.time_helpers import is_during_target_window
from dotenv import load_dotenv
import os

load_dotenv()

LOG_ALL_REACTIONS = os.getenv("LOG_ALL_REACTONS", "false").lower() == "true"


class Reactions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is added to a message."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return  # DM or unknown guild

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return  # Ensure it's a text channel

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)

        if user and user.bot:
            print(f"Ignoring bot reaction from {user.name}")
            return

        if user:
            if (
                payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS.value
                and (
                    (
                        "friday" in message.content.lower()
                        and is_during_target_window(DayOfWeek.FRIDAY.value)
                    )
                    or (
                        "sunday" in message.content.lower()
                        and is_during_target_window(DayOfWeek.SUNDAY.value)
                    )
                )
            ):
                log_channel = self.bot.get_channel(
                    ChannelIds.SERVING__DRIVER_BOT_SPAM.value
                )
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTIONS:
                log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is removed from a message."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)

        if user and user.bot:
            print(f"Ignoring bot reaction removal from {user.name}")
            return

        if user:
            if (
                payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS.value
                and (
                    (
                        "friday" in message.content.lower()
                        and is_during_target_window(DayOfWeek.FRIDAY.value)
                    )
                    or (
                        "sunday" in message.content.lower()
                        and is_during_target_window(DayOfWeek.SUNDAY.value)
                    )
                )
            ):
                log_channel = self.bot.get_channel(
                    ChannelIds.SERVING__DRIVER_BOT_SPAM.value
                )
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTIONS:
                log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reactions(bot))
