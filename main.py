"""Main functionality of bot"""


from discord.ext import commands, tasks
from discord import app_commands
# Built in modules
import copy
import json
import os
from typing import Dict, List, Set, Union, Callable, Any
import requests
import csv
from collections import defaultdict
from pprint import pprint
from datetime import datetime, timedelta
# External modules
import discord
# from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import yaml

# Local modules
from logger import logger
import utils.ping as ping
import utils.constants as constants

# if "dev" in os.getenv('BOT_ENV').lower():
#     print("DEV")

#     # Environment variables from .env file
#     load_dotenv('.env.dev')
#     # TOKEN: str = os.getenv('TOKEN')
#     # BOT_NAME: str = os.getenv('BOT_NAME')
#     # # LOCATIONS_PATH: str = os.getenv('LOCATIONS_PATH')
#     # # EMERGENCY_CONTACT: int = int(os.getenv('EMERGENCY_CONTACT'))
    
#     # GUILD_ID: int = int(os.getenv('GUILD_ID'))


#     TOKEN: str = os.environ['TOKEN']
#     BOT_NAME: str = os.environ['BOT_NAME']
#     GUILD_ID: int = int(os.environ['GUILD_ID'])
#     DRIVERS_CHANNEL: int = int(os.environ['DRIVERS_CHANNEL'])
if os.getenv('BOT_ENV') and "prod" in os.getenv('BOT_ENV').lower():
    TOKEN: str = os.environ['TOKEN']
    BOT_NAME: str = os.environ['BOT_NAME']
    CSV_URL: str = os.environ['CSV_URL']
    GUILD_ID: int = int(os.environ['GUILD_ID'])
    DRIVERS_CHANNEL: int = int(os.environ['DRIVERS_CHANNEL'])
else:
    load_dotenv()
    TOKEN: str = os.environ['TOKEN']
    BOT_NAME: str = os.environ['BOT_NAME']
    GUILD_ID: int = int(os.environ['GUILD_ID'])
    DRIVERS_CHANNEL: int = int(os.environ['DRIVERS_CHANNEL'])
    CSV_URL: str = os.environ['CSV_URL']


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

LOCATIONS_CHANNELS_WHITELIST = [SERVING_BOT_SPAM_CHANNEL_ID, LEADERSHIP_CHANNEL_ID, DRIVER_CHANNEL_ID, BOTS_CHANNEL_ID, BOT_SPAM_2_CHANNEL_ID, ]


SCHOLARS_LOCATIONS = ["revelle", "muir", "sixth", "marshall", "erc", "seventh"]


def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.all()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)


    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s).")
        except Exception as e:      # pylint: disable=W0718
            print(e)


    @bot.tree.command(name="ask-drivers", description="Pings drivers to see who is available")
    async def ask_drivers(interaction: discord.Interaction, message: str) -> None:
        
  
        logger.info("ask-drivers command was executed")

        channel = bot.get_channel(DRIVERS_CHANNEL) # Currently on dev channel
        message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.DRIVERS_ROLE_ID),
                                                                 message)
        sent_message = await channel.send(message_to_send)
        await sent_message.add_reaction("👍")  
        await sent_message.add_reaction("❌")  
        await sent_message.add_reaction("➡️")  
        await sent_message.add_reaction("⬅️")  
        await sent_message.add_reaction("💩")  

        # There needs to be something sent 
        await interaction.response.send_message("Message sent!", delete_after=0)

    @bot.tree.command(name="test", description="test")
    async def test(interaction: discord.Interaction) -> None:
        # Get the current date and time
        now = datetime.now()

        

        # Check if today is Sunday
        if now.weekday() == 6:  # Sunday is represented by 6
            # If today is Sunday, get the previous Sunday
            last_sunday = now - timedelta(days=7)
        else:
            # If today is not Sunday, get the most recent Sunday
            last_sunday = now - timedelta(days=(now.weekday() + 1))

        # Get the channel by its ID
        channel = bot.get_channel(RIDES_CHANNEL_ID)
        most_recent_message = None 
        if channel is not None:
            # Fetch messages since last Sunday
            async for message in channel.history(after=last_sunday):
                # Check if message contains both "Sunday" and "@Rides"
                AT_RIDES = "<@&940467850261450752>"
                if AT_RIDES in message.content and "sunday" in message.content.lower() and "react" in message.content.lower():
                    print(f'Message found: {message.content}')
                    print(f'Message ID: {message.id}')
                    most_recent_message = message
                    
        if most_recent_message is None:
            # If no matching message was found, return None
            print('No matching message found')
            await interaction.response.send_message("None found")

        await interaction.response.send_message(most_recent_message.id)
        return most_recent_message.id  # Return the message ID
    
    @bot.tree.command(name="pickup-location", description="Pickup location for a person, include the name or Discord username")
    async def pickup_location(interaction: discord.Interaction, name: str) -> None:
        logger.info(f"pickup-location command was executed by {interaction.user} in #{interaction.channel}") 
        
        if not interaction.channel_id in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message("Command cannot be used in this channel.")
            logger.info(f"pickup-location not allowed in #{interaction.channel} by {interaction.user}") 
            return


        response = requests.get(CSV_URL)

        # Check if the request was successful
        if response.status_code == 200:
            # Decode the content as text
            csv_data = response.content.decode('utf-8')

            # Use csv.reader to parse the content
            csv_reader = csv.reader(csv_data.splitlines(), delimiter=',')

            print(csv_reader)


            possible_people = []


            # Loop through rows in the CSV
            for row in csv_reader:
                for idx, cell in enumerate(row):

                    if name.lower() in cell.lower():
                        try:
                            location = row[idx+1].strip()
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


    @bot.tree.command(name="my-car", description="Pings all people placed in car")
    async def ping_my_car(interaction: discord.Interaction, message_to_car: str) -> None:
    


        # Get the current date and time
        now = datetime.now()

        # Check if today is Sunday
        if now.weekday() == 6:  # Sunday is represented by 6
            # If today is Sunday, get the previous Sunday
            last_sunday = now - timedelta(days=7)
        else:
            # If today is not Sunday, get the most recent Sunday
            last_sunday = now - timedelta(days=(now.weekday() + 1))

        # Get the channel by its ID
        channel = bot.get_channel(BOTS_CHANNEL_ID)

        mentioned_usernames_real_message = None

        if channel is not None:
            # Fetch messages since last Sunday
            async for message in channel.history(after=last_sunday):
                mentioned_usernames = [user.name for user in message.mentions]
                if interaction.user.name in mentioned_usernames and "drive" in message.content.lower() and ":" in message.content.lower():
                    mentioned_usernames_real_message = [user.name for user in message.mentions]

        to_send = ""
        for username in mentioned_usernames_real_message:
            if interaction.user.name == username:
                continue 
            to_send += discord.utils.find(lambda u: u.name == username, channel.guild.members).mention
        
        to_send += f""" {message_to_car} - {interaction.user.display_name} """
        await interaction.response.send_message(to_send)
        

    @bot.tree.command(name="list-pickups-sunday", description="Locations of pickups for sunday service")
    async def list_locations_sunday(interaction: discord.Interaction) -> None:
        await list_locations(interaction, "sunday")

    @bot.tree.command(name="list-pickups-friday", description="Locations of pickups for friday fellowship")
    async def list_locations_friday(interaction: discord.Interaction) -> None:
        await list_locations(interaction, "friday")

    async def list_locations(interaction, day):
        logger.info(f"list-drivers command was executed by {interaction.user} in #{interaction.channel}") 
        
        if not interaction.channel_id in LOCATIONS_CHANNELS_WHITELIST:
            await interaction.response.send_message("Command cannot be used in this channel.")
            logger.info(f"list-drivers not allowed in #{interaction.channel} by {interaction.user}") 
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

        # Get the channel by its ID
        channel = bot.get_channel(RIDES_CHANNEL_ID)
        most_recent_message = None 
        if channel is not None:
            # Fetch messages since last Sunday
            async for message in channel.history(after=last_sunday):
                # Check if message contains both "Sunday" and "@Rides"
                AT_RIDES = "<@&940467850261450752>"
                if day in message.content.lower() and "react" in message.content.lower():
                    print(f'Message found: {message.content}')
                    print(f'Message ID: {message.id}')
                    most_recent_message = message
                    
        if most_recent_message is None:
            # If no matching message was found, return None
            print('No matching message found')
            await interaction.response.send_message("No message found")
            return

        # await interaction.response.send_message(most_recent_message.id)
        # return most_recent_message.id  # Return the message ID

        message_id = most_recent_message.id

       
        usernames_reacted = set()
        channel = bot.get_channel(RIDES_CHANNEL_ID)   # Channel ID
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
            csv_data = response.content.decode('utf-8')

            # Use csv.reader to parse the content
            csv_reader = csv.reader(csv_data.splitlines(), delimiter=',')

            print(csv_reader)

            locations_people = defaultdict(list)

            location_found = set()

            # Loop through rows in the CSV
            for row in csv_reader:
                for idx, cell in enumerate(row):
                    for username in usernames_reacted:
                        
                        if str(username) in cell:
                            name = cell
                            location = row[idx+1].strip()
                            locations_people[location].append(name[:name.index("(")-1])
                            location_found.add(username)



            scholars_people = ""
            warren_pcyn_people = ""
            rita_people = ""
            off_campus_people = ""

            scholars_count, warren_pcyn_count, rita_count, off_campus_count = (0,0,0,0)


            for location in locations_people:

                if location.lower() in SCHOLARS_LOCATIONS or len([l for l in SCHOLARS_LOCATIONS if l in location.lower()]) > 0:
                    scholars_count += len(locations_people[location])
                    scholars_people += f"({len(locations_people[location])}) {location}: {', '.join(locations_people[location])}\n"
                elif "warren" in location.lower() or "pcyn" in location.lower():
                    warren_pcyn_count += len(locations_people[location])
                    warren_pcyn_people += f"({len(locations_people[location])}) {location}: {', '.join(locations_people[location])}\n"
                elif "rita" in location.lower() or "eighth" in location.lower():
                    rita_count += len(locations_people[location])
                    rita_people += f"({len(locations_people[location])}) {location}: {', '.join(locations_people[location])}\n"
                else:
                    off_campus_count += len(locations_people[location])
                    off_campus_people += f"({len(locations_people[location])}) {location}: {', '.join(locations_people[location])}\n"

                # print(f"{location}: {', '.join(locations_people[location])}")
            output = ""
            output += f"__[{scholars_count}] Scholars (no eighth)__\n" + scholars_people if scholars_count > 0 else ""
            output += "--\n" + f"__[{warren_pcyn_count}] Warren + Peppercanyon__\n" + warren_pcyn_people if warren_pcyn_count > 0 else ""
            output += "--\n" + f"__[{rita_count}] Rita + Eighth__\n" + rita_people if rita_count > 0 else ""
            output += "--\n" + f"__[{off_campus_count}] Off campus__\n" + off_campus_people if off_campus_count > 0 else ""
            # print(f"({scholars_count})\n" + scholars_people + "--\n" + f"({warren_pcyn_count})\n" + warren_pcyn_people + "--\n" + f"({rita_count})\n" + rita_people + "--\n" + f"({off_campus_count})\n" + off_campus_people)
                    
            unknown_location = set(usernames_reacted) - location_found
            unknown_location = [str(user) for user in unknown_location]
            print("==============")
            print(type(unknown_location))
            if len(unknown_location) > 0:
                output += f"\nUnknown location: {', '.join(unknown_location)} (make sure their full discord username is in the google sheet)"


        else:
            print("Failed to retrieve the CSV file")
            output = "Error occurred"


        await interaction.response.send_message(output)

    bot.run(TOKEN)


if __name__ == "__main__":
    run()
