import discord
from discord.ext import commands

from enums import ChannelIds, DaysOfWeek, RoleIds
from utils.time_helpers import is_during_target_window
from dotenv import load_dotenv
import os
import requests
import csv

load_dotenv()

LOG_ALL_REACTIONS = os.getenv("LOG_ALL_REACTONS", "false").lower() == "true"
TARGET_MESSAGE_ID = 940467929676406807
TARGET_CHANNEL_ID = 916821529663250463
TARGET_CATEGORY_ID = 1380694503391887410
CSV_URL = os.getenv("CSV_URL")


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
            if payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS and (
                (
                    "friday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.FRIDAY)
                )
                or (
                    "sunday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.SUNDAY)
                )
            ):
                log_channel = self.bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTIONS:
                log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )

            def we_have_location(username):
                response = requests.get(CSV_URL, timeout=60)

                csv_data = response.content.decode("utf-8")
                csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

                for row in csv_reader:
                    for _, cell in enumerate(row):
                        if str(username) in cell.lower():
                            return True

                return False

            if (
                payload.message_id == TARGET_MESSAGE_ID
                and payload.channel_id == TARGET_CHANNEL_ID
                and user is not None
                and not we_have_location(user.name.lower())
            ):
                channel_name = f"{user.name.lower()}"
                category = discord.utils.get(guild.categories, id=TARGET_CATEGORY_ID)

                if not category:
                    print(f"Category with ID {TARGET_CATEGORY_ID} not found.")
                    return

                existing_channel = discord.utils.get(
                    category.channels, name=channel_name
                )
                if existing_channel:
                    print(f"Channel {channel_name} already exists.")
                    return

                # Permissions

                role = guild.get_role(RoleIds.RIDE_COORDINATOR)

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    user: discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    ),
                    role: discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    ),
                }

                for role in guild.roles:
                    if role.permissions.administrator:
                        overwrites[role] = discord.PermissionOverwrite(
                            read_messages=True, send_messages=True
                        )

                new_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    reason=f"{user.name} reacted for rides.",
                )

                await new_channel.send(
                    f"Hi {user.mention}! Thanks for reacting in for rides in <#{TARGET_CHANNEL_ID}>. "
                    "We don’t yet know where to pick you up. "
                    "If you live **on campus**, please share the college or neighborhood where you live (e.g., Sixth, Pepper Canyon West, Rita). "
                    "If you live **off campus**, please share your apartment complex or address. "
                    "One of our ride coordinators will check in with you shortly!"
                )
                return

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
            if payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS and (
                (
                    "friday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.FRIDAY)
                )
                or (
                    "sunday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.SUNDAY)
                )
            ):
                log_channel = self.bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTIONS:
                log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reactions(bot))
