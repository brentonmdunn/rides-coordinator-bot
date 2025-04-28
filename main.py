"""Main functionality of bot"""

from discord.ext import commands, tasks
from discord import app_commands

# Built in modules
import copy
import json
import os
from typing import Dict, List, Set, Union, Callable, Any
import re
import requests
import csv
from collections import defaultdict
from pprint import pprint
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

# External modules
import discord

# from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import yaml
import pytz

# Local modules
from logger import logger
import utils.ping as ping
import utils.constants as constants
from utils.csv_fetcher import CSVFetcher


if os.getenv("BOT_ENV") and "prod" in os.getenv("BOT_ENV").lower():
    TOKEN: str = os.environ["TOKEN"]
    CSV_URL: str = os.environ["CSV_URL"]
    LOG_ALL_REACTONS = os.environ["LOG_ALL_REACTONS"].lower() == "true"
else:
    load_dotenv()
    TOKEN: str = os.environ["TOKEN"]
    CSV_URL: str = os.environ["CSV_URL"]
    LOG_ALL_REACTONS: bool = os.environ["LOG_ALL_REACTONS"].lower() == "true"


# Global variables
# message_id: int = 0
# channel_id: int = 0
# new_message = ""

LEADERSHIP_CHANNEL_ID = 1155357301050449931
DRIVER_CHANNEL_ID = 1286925673004269601
SUNDAY_SERVICE_CHANNEL_ID = 1286942023894433833
BOTS_CHANNEL_ID = 916823070017204274
BOT_SPAM_2_CHANNEL_ID = 1208264072638898217
RIDES_CHANNEL_ID = 939950319721406464
SERVING_BOT_SPAM_CHANNEL_ID = 1297323073594458132

LOCATIONS_CHANNELS_WHITELIST = [
    SERVING_BOT_SPAM_CHANNEL_ID,
    LEADERSHIP_CHANNEL_ID,
    DRIVER_CHANNEL_ID,
    BOTS_CHANNEL_ID,
    BOT_SPAM_2_CHANNEL_ID,
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
            if payload.channel_id == RIDES_CHANNEL_ID and (
                ("friday" in message.content.lower() and is_within_time_range("friday"))
                or (
                    "sunday" in message.content.lower()
                    and is_within_time_range("sunday")
                )
            ):
                log_channel = bot.get_channel(SERVING_BOT_SPAM_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTONS:
                log_channel = bot.get_channel(1208482668820570162)
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
            if payload.channel_id == RIDES_CHANNEL_ID and (
                ("friday" in message.content.lower() and is_within_time_range("friday"))
                or (
                    "sunday" in message.content.lower()
                    and is_within_time_range("sunday")
                )
            ):
                log_channel = bot.get_channel(SERVING_BOT_SPAM_CHANNEL_ID)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} unreacted {payload.emoji} to message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
                return

            if LOG_ALL_REACTONS:
                log_channel = bot.get_channel(1208482668820570162)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} removed their reaction {payload.emoji} from message '{discord.utils.escape_mentions(message.content)}' in #{channel.name}"
                    )
            # print(f"{user.name} removed their reaction {payload.emoji} from message '{message.content}' in #{channel.name}")

    def is_within_time_range(day):
        """Checks if the current time in LA is within:
        - Thursday 7 PM to Friday 7 PM
        - Saturday 10 AM to Sunday 10 AM
        """
        LA_TZ = pytz.timezone("America/Los_Angeles")  # Los Angeles Time Zone
        now = datetime.now().astimezone(LA_TZ)  # Get current LA time
        weekday = now.weekday()  # Monday = 0, Sunday = 6
        hour = now.hour

        # Check Thursday 7 PM (3, 19) → Friday 7 PM (4, 19)
        if day == "friday" and (
            (weekday == 3 and hour >= 19) or (weekday == 4 and hour < 19)
        ):
            return True

        # Check Saturday 10 AM (5, 10) → Sunday 10 AM (6, 10)
        if day == "sunday" and (
            (weekday == 5 and hour >= 10) or (weekday == 6 and hour < 10)
        ):
            return True

        return False

    # def is_within_time_range_tester():
    #     """Checks if the current time in PST is between Thursday 7 PM and Friday 7 PM."""
    #     LA_TZ = pytz.timezone("America/Los_Angeles")  # Los Angeles Time Zone
    #     now = datetime.now().astimezone(LA_TZ)
    #     weekday = now.weekday()  # Monday = 0, Sunday = 6
    #     hour = now.hour

    #     # Thursday 7 PM (weekday 3) to Friday 7 PM (weekday 4)
    #     if (weekday == 0 and hour >= 12):
    #         return True
    #     return False

    # @bot.event
    # async def on_reaction_add_raw(reaction, user):
    #     """Logs reactions when someone reacts to a tracked message"""
    #     if user.bot:
    #         return  # Ignore bot reactions

    #     message_id = reaction.message.id

    # log_channel = bot.get_channel(1208482668820570162)
    # print("jdsflajfljsal")
    # if log_channel:
    #     await log_channel.send(f"{user.name} reacted {reaction.emoji} to the tracked message.")
    #     # if message_id in tracked_messages:
    #     #     log_channel = bot.get_channel(LOG_CHANNEL_ID)
    #     #     if log_channel:
    #     #         await log_channel.send(f"{user.name} reacted {reaction.emoji} to the tracked message.")

    # @bot.tree.command(name="broadcast", description="Send message to multiple channels")
    # async def boradcast(interaction: discord.Interaction, message: str) -> None:
    #     clist = [1338047132115931177, 1338047266237452310, 1338047339729780767, 1338047388258140234, 1338047409627988000]
    #     for c in clist:
    #         channel = bot.get_channel(c)
    #         await channel.send(message)

    #     await interaction.response.send_message("success")

    def parse_name(text):
        """
        Parse the input string to extract the name and username.

        Args:
            input_string (str): The input string to parse.

        Returns:
            tuple: A tuple containing the name and username.
        """
        # pattern = r"(.*)\s*($[^)]+$)?"
        # match = re.match(pattern, input_string)

        # if match:
        #     name = match.group(1).strip()
        #     username = match.group(2)

        #     if username:
        #         username = username[1:-1]  # Remove parentheses
        #     else:
        #         username = None

        #     return name, username
        # else:
        #     return None, None

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

            print(csv_reader)

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
        if interaction.channel_id != DRIVER_CHANNEL_ID:
            await interaction.response.send_message(
                f"`/ask-drivers` can only be used in <#{DRIVER_CHANNEL_ID}>"
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

    @bot.tree.command(
        name="pickup-location",
        description="Pickup location for a person, include the name or Discord username",
    )
    async def pickup_location(interaction: discord.Interaction, name: str) -> None:
        logger.info(
            f"pickup-location command was executed by {interaction.user} in #{interaction.channel}"
        )

        if not interaction.channel_id in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel."
            )
            logger.info(
                f"pickup-location not allowed in #{interaction.channel} by {interaction.user}"
            )
            return

        response = requests.get(CSV_URL)

        # Check if the request was successful
        if response.status_code == 200:
            # Decode the content as text
            csv_data = response.content.decode("utf-8")

            # Use csv.reader to parse the content
            csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")
            possible_people = []

            # Loop through rows in the CSV
            for row in csv_reader:
                for idx, cell in enumerate(row):
                    if name.lower() in cell.lower():
                        try:
                            location = row[idx + 1].strip()
                            possible_people.append((cell, location))
                        except:
                            pass

            if len(possible_people) == 0:
                await interaction.response.send_message("No people found")
                return

            output = ""
            for idx, (name, location) in enumerate(possible_people):
                if idx != 0:
                    output += "\n"
                output += f"{name}: {location}"
        await interaction.response.send_message(output)

    # @bot.tree.command(name="my-car", description="Pings all people placed in car")
    # async def ping_my_car(interaction: discord.Interaction, message_to_car: str) -> None:

    #     # Get the current date and time
    #     now = datetime.now()

    #     # Check if today is Sunday
    #     if now.weekday() == 6:  # Sunday is represented by 6
    #         # If today is Sunday, get the previous Sunday
    #         last_sunday = now - timedelta(days=7)
    #     else:
    #         # If today is not Sunday, get the most recent Sunday
    #         last_sunday = now - timedelta(days=(now.weekday() + 1))

    #     # Get the channel by its ID
    #     channel = bot.get_channel(BOTS_CHANNEL_ID)

    #     mentioned_usernames_real_message = None

    #     if channel is not None:
    #         # Fetch messages since last Sunday
    #         async for message in channel.history(after=last_sunday):
    #             mentioned_usernames = [user.name for user in message.mentions]
    #             if interaction.user.name in mentioned_usernames and "drive" in message.content.lower() and ":" in message.content.lower():
    #                 mentioned_usernames_real_message = [user.name for user in message.mentions]

    #     to_send = ""
    #     for username in mentioned_usernames_real_message:
    #         if interaction.user.name == username:
    #             continue
    #         to_send += discord.utils.find(lambda u: u.name == username, channel.guild.members).mention

    #     to_send += f""" {message_to_car} - {interaction.user.display_name} """
    #     await interaction.response.send_message(to_send)

    @bot.tree.command(
        name="list-pickups-sunday",
        description="Locations of pickups for sunday service",
    )
    async def list_locations_sunday(interaction: discord.Interaction) -> None:
        await list_locations(interaction, "sunday")

    @bot.tree.command(
        name="list-pickups-friday",
        description="Locations of pickups for friday fellowship",
    )
    async def list_locations_friday(interaction: discord.Interaction) -> None:
        await list_locations(interaction, "friday")

    @bot.tree.command(
        name="list-pickups-by-message-id",
        description="Locations of pickups for a specific message",
    )
    async def list_locations_unknown(
        interaction: discord.Interaction, message_id: str
    ) -> None:
        await list_locations(interaction, message_id=message_id)

    async def list_locations(interaction, day=None, message_id=None):
        logger.info(
            f"list-drivers command was executed by {interaction.user} in #{interaction.channel}"
        )

        if not interaction.channel_id in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message(
                "Command cannot be used in this channel."
            )
            logger.info(
                f"list-drivers not allowed in #{interaction.channel} by {interaction.user}"
            )
            return

        # Get the current date and time
        now = datetime.now()

        # Check if today is Sunday
        if now.weekday() == 6:  # Sunday is represented by 6
            # If today is Sunday, get the previous Sunday
            last_sunday = now - timedelta(days=7)
        else:
            # If today is not Sunday, get the most recent Sunday
            last_sunday = now - timedelta(days=(now.weekday() + 1))

        if day is not None:
            # Get the channel by its ID
            channel = bot.get_channel(RIDES_CHANNEL_ID)
            most_recent_message = None
            if channel is not None:
                # Fetch messages since last Sunday
                async for message in channel.history(after=last_sunday):
                    # Check if message contains both "Sunday" and "@Rides"
                    AT_RIDES = "<@&940467850261450752>"
                    if (
                        day in message.content.lower()
                        and "react" in message.content.lower()
                    ):
                        print(f"Message found: {message.content}")
                        print(f"Message ID: {message.id}")
                        most_recent_message = message

            if most_recent_message is None:
                # If no matching message was found, return None
                print("No matching message found")
                await interaction.response.send_message("No message found")
                return

            message_id = most_recent_message.id

        usernames_reacted = set()
        channel = bot.get_channel(RIDES_CHANNEL_ID)  # Channel ID
        try:
            message = await channel.fetch_message(message_id)
            reactions = message.reactions
            for reaction in reactions:
                async for user in reaction.users():
                    usernames_reacted.add(user)

        except Exception as e:
            print(f"Error: {e}")

        response = requests.get(CSV_URL)

        # Check if the request was successful
        if response.status_code == 200:
            # Decode the content as text
            csv_data = response.content.decode("utf-8")

            # Use csv.reader to parse the content
            csv_reader = csv.reader(csv_data.splitlines(), delimiter=",")

            print(csv_reader)

            locations_people = defaultdict(list)

            location_found = set()

            # Loop through rows in the CSV
            for row in csv_reader:
                for idx, cell in enumerate(row):
                    for username in usernames_reacted:
                        if str(username) in cell:
                            name = cell
                            location = row[idx + 1].strip()
                            locations_people[location].append(
                                name[: name.index("(") - 1]
                            )
                            location_found.add(username)

            scholars_people = ""
            warren_pcyn_people = ""
            rita_people = ""
            off_campus_people = ""

            scholars_count, warren_pcyn_count, rita_count, off_campus_count = (
                0,
                0,
                0,
                0,
            )

            embed = discord.Embed(title="Housing Breakdown", color=discord.Color.blue())

            for location in locations_people:
                if (
                    location.lower() in SCHOLARS_LOCATIONS
                    or len([l for l in SCHOLARS_LOCATIONS if l in location.lower()]) > 0
                ):
                    scholars_count += len(locations_people[location])
                    scholars_people += f"**({len(locations_people[location])}) {location}:** {', '.join(locations_people[location])}\n"
                elif "warren" in location.lower() or "pcyn" in location.lower():
                    warren_pcyn_count += len(locations_people[location])
                    warren_pcyn_people += f"**({len(locations_people[location])}) {location}:** {', '.join(locations_people[location])}\n"
                elif "rita" in location.lower() or "eighth" in location.lower():
                    rita_count += len(locations_people[location])
                    rita_people += f"**({len(locations_people[location])}) {location}:** {', '.join(locations_people[location])}\n"
                else:
                    off_campus_count += len(locations_people[location])
                    off_campus_people += f"**({len(locations_people[location])}) {location}:** {', '.join(locations_people[location])}\n"

            if scholars_count > 0:
                embed.add_field(
                    name=f"🏫 [{scholars_count}] Scholars (no eighth)",
                    value=scholars_people,
                    inline=False,
                )

            if warren_pcyn_count > 0:
                embed.add_field(
                    name=f"🏠 [{warren_pcyn_count}] Warren + Pepper Canyon",
                    value=warren_pcyn_people,
                    inline=False,
                )

            if rita_count > 0:
                embed.add_field(
                    name=f"🏡 [{rita_count}] Rita + Eighth",
                    value=rita_people,
                    inline=False,
                )

            if off_campus_count > 0:
                embed.add_field(
                    name=f"🌍 [{off_campus_count}] Off Campus",
                    value=off_campus_people,
                    inline=False,
                )

            unknown_location = set(usernames_reacted) - location_found
            unknown_location = [str(user) for user in unknown_location]
            if len(unknown_location) > 0:
                embed.add_field(
                    name=f"❓ [{len(unknown_location)}] Unknown Location",
                    value=f"{', '.join(unknown_location)} (make sure their full discord username is in the google sheet)",
                    inline=False,
                )

            # output = ""
            # output += f"__[{scholars_count}] Scholars (no eighth)__\n" + scholars_people if scholars_count > 0 else ""
            # output += "--\n" + f"__[{warren_pcyn_count}] Warren + Peppercanyon__\n" + warren_pcyn_people if warren_pcyn_count > 0 else ""
            # output += "--\n" + f"__[{rita_count}] Rita + Eighth__\n" + rita_people if rita_count > 0 else ""
            # output += "--\n" + f"__[{off_campus_count}] Off campus__\n" + off_campus_people if off_campus_count > 0 else ""
            # # print(f"({scholars_count})\n" + scholars_people + "--\n" + f"({warren_pcyn_count})\n" + warren_pcyn_people + "--\n" + f"({rita_count})\n" + rita_people + "--\n" + f"({off_campus_count})\n" + off_campus_people)

            # unknown_location = set(usernames_reacted) - location_found
            # unknown_location = [str(user) for user in unknown_location]
            # print("==============")
            # print(type(unknown_location))
            # if len(unknown_location) > 0:
            #     output += f"\nUnknown location: {', '.join(unknown_location)} (make sure their full discord username is in the google sheet)"

            await interaction.response.send_message(embed=embed)

        else:
            print("Failed to retrieve the CSV file")
            output = "Error occurred"

            await interaction.response.send_message(output)

    @bot.tree.command(
        name="list-pickups-retreat",
        description="Locations of pickups for retreat",
    )
    async def list_locations_retreat(
        interaction: discord.Interaction, message_id: str
    ) -> None:
        
        fetcher = CSVFetcher(os.getenv("RETREAT_RIDES_CSV_URL"), True)
        

    bot.run(TOKEN)


if __name__ == "__main__":
    run()
