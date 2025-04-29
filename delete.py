"""Main functionality of bot"""

# Built in modules
from collections import defaultdict
import csv
from datetime import datetime, timedelta
import os
import re
import requests

# External modules
import discord
from discord.ext import commands
from dotenv import load_dotenv
import pytz

# Local modules
from logger import logger
import utils.constants as constants
from enums import ChannelIds, DayOfWeek

if os.getenv("BOT_ENV") and "prod" in os.getenv("BOT_ENV").lower():
    TOKEN: str = os.environ["TOKEN"]
    CSV_URL: str = os.environ["CSV_URL"]
    LOG_ALL_REACTONS = os.environ["LOG_ALL_REACTONS"].lower() == "true"
else:
    load_dotenv()
    TOKEN: str = os.environ["TOKEN"]
    CSV_URL: str = os.environ["CSV_URL"]
    LOG_ALL_REACTONS: bool = os.environ["LOG_ALL_REACTONS"].lower() == "true"


LOCATIONS_CHANNELS_WHITELIST = [
    ChannelIds.SERVING__DRIVER_BOT_SPAM.value,
    ChannelIds.SERVING__LEADERSHIP.value,
    ChannelIds.SERVING__DRIVER_CHAT_WOOOOO.value,
    ChannelIds.BOT_STUFF__BOTS.value,
    ChannelIds.BOT_STUFF__BOT_SPAM_2.value,
]


SCHOLARS_LOCATIONS = ["revelle", "muir", "sixth", "marshall", "erc", "seventh"]


def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.all()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s).")
        except Exception as e:  # pylint: disable=W0718
            print(e)

    @bot.event
    async def on_message(message):
        if message.author.bot:  # Ignore bot messages
            return

        if "what the sigma" in message.content.lower():
            # await message.reply("yellow")  # Properly replies to the message
            await message.add_reaction("❌")

        await bot.process_commands(message)  # Ensures other commands still work

    @bot.event
    async def on_raw_reaction_add(payload):
        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return  # DM or unknown guild

        channel = bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return  # Ensure it's a text channel

        message = await channel.fetch_message(payload.message_id)  # Fetch the message

        user = guild.get_member(payload.user_id)

        # Check if the reaction is from a bot
        if user and user.bot:
            print(f"Ignoring bot reaction from {user.name}")
            return

        if user and not user.bot:
            # 7PM thursday to 7PM friday or 10AM saturday to 10AM sunday notification
            if (
                payload.channel_id == ChannelIds.REFEREMCES__RIDES_ANNOUNCEMENTS.value
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
                log_channel = bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTONS:
                log_channel = bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )

    @bot.event
    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
        """Logs when a reaction is removed."""
        guild = bot.get_guild(payload.guild_id)
        if guild is None:
            return  # DM or unknown guild

        channel = bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return  # Ensure it's a text channel

        message = await channel.fetch_message(payload.message_id)  # Fetch the message
        user = guild.get_member(payload.user_id)

        if user and user.bot:
            print(f"Ignoring bot reaction removal from {user.name}")
            return

        if user:
            # 7PM thursday to 7PM friday or 10AM saturday to 10AM sunday notification
            if (
                payload.channel_id == ChannelIds.REFEREMCES__RIDES_ANNOUNCEMENTS.value
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
                log_channel = bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} unreacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTONS:
                log_channel = bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS.value)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
            # print(f"{user.name} removed their reaction {payload.emoji} from message '{message.content}' in #{channel.name}")

    def is_during_target_window(day: str) -> bool:
        """Checks if the current time in LA is within:
        - Thursday 7 PM to Friday 7 PM
        - Saturday 10 AM to Sunday 10 AM
        """
        LA_TZ = pytz.timezone("America/Los_Angeles")
        now = datetime.now().astimezone(LA_TZ)
        weekday_index = now.weekday()  # Monday = 0, Sunday = 6
        hour = now.hour

        # Map weekday index (int) to DayOfWeek enum
        weekday_enum = list(DayOfWeek)[weekday_index]

        try:
            day_enum = DayOfWeek(day.capitalize())
        except ValueError:
            return False  # Invalid day passed in

        if day_enum == DayOfWeek.FRIDAY:
            return (weekday_enum == DayOfWeek.THURSDAY and hour >= 19) or (
                weekday_enum == DayOfWeek.FRIDAY and hour < 19
            )

        if day_enum == DayOfWeek.SUNDAY:
            return (weekday_enum == DayOfWeek.SATURDAY and hour >= 10) or (
                weekday_enum == DayOfWeek.SUNDAY and hour < 10
            )

        return False

    def parse_name(text):
        """
        Parse the input string to extract the name and username.

        Args:
            input_string (str): The input string to parse.

        Returns:
            tuple: A tuple containing the name and username.
        """
        match = re.match(r"^(.*?)\s*\((.*?)\)$", text)
        if match:
            return match.group(1), match.group(2)
        return text, None

    @bot.tree.command(
        name="whois", description="List name and Discord username of potential matches"
    )
    async def whois(interaction: discord.Interaction, name: str) -> None:
        response = requests.get(CSV_URL)

        saved_name = None
        discord_username = None

        # Check if the request was successful
        if response.status_code == 200:
            # Decode the content as text
            csv_data = response.content.decode("utf-8")

            # Use csv.reader to parse the content
            csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

            message = ""

            # Loop through rows in the CSV
            for row in csv_reader:
                for _, cell in enumerate(row):
                    if name in cell:
                        saved_name, discord_username = parse_name(cell)
                        if saved_name is not None:
                            message += f"\nname: {saved_name}"
                        if discord_username is not None:
                            message += f"\ndiscord: {discord_username}"

        await interaction.response.send_message(message)

    @bot.tree.command(name="help-rides", description="Available commands for ride bot")
    async def help_rides(interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="Ride Bot Commands", color=discord.Color.blue())

        embed.add_field(
            name="`/ask-drivers <message>`",
            value="Pings drivers to see who is available to drive",
            inline=False,
        )

        embed.add_field(
            name="`/pickup-location <name or username>`",
            value="Outputs the pickup location for specified name or username",
            inline=False,
        )

        embed.add_field(
            name="`/list-pickups-friday`",
            value="Outputs a breakdown of who reacted for a ride for Friday fellowship and where to pick them up",
            inline=False,
        )

        embed.add_field(
            name="`/list-pickups-sunday`",
            value="Outputs a breakdown of who reacted for a ride for Sunday service and where to pick them up",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name="ask-drivers", description="Pings drivers to see who is available"
    )
    async def ask_drivers(interaction: discord.Interaction, message: str) -> None:
        if interaction.channel_id != ChannelIds.SERVING__DRIVER_CHAT_WOOOOO.value:
            await interaction.response.send_message(
                f"`/ask-drivers` can only be used in <#{ChannelIds.SERVING__DRIVER_CHAT_WOOOOO.value}>"
            )
            return

        message_to_send = f"<@&{constants.DRIVERS_ROLE_ID}> {message}"

        # Allow role mentions
        await interaction.response.send_message(
            message_to_send, allowed_mentions=discord.AllowedMentions(roles=True)
        )

        # Fetch the sent message
        sent_message = await interaction.original_response()

        # Add reactions
        reactions = ["👍", "❌", "➡️", "⬅️", "💩"]
        for reaction in reactions:
            await sent_message.add_reaction(reaction)

    bot.run(TOKEN)


if __name__ == "__main__":
    run()
