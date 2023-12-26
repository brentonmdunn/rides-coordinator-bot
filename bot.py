"""Main functionality of bot"""

import json
import os
import random
from typing import Dict, List, Set

import discord
from dotenv import load_dotenv

import utils.ping as ping

# Environment variables from .env file
load_dotenv()
TOKEN = os.getenv('TOKEN')
BOT_NAME = os.getenv('BOT_NAME')

# Constants
RIDES_MESSAGE: str = "React for rides."
REACTS: List[str] = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']
ROLE_ID: int = 1188019586470256713
LOCATIONS_PATH = "locations.json"

# Global variables
needs_ride: List[str] = []
drivers: List[str] = []
current_reaction: int = 0
message_id: int = None

def run():

    intents: discord.Intents = discord.Intents.all()
    intents.message_content = True
    client: discord.Client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        """Prints on start"""
        print(f"{client.user} is running.")

    @client.event
    async def on_message(message):
        """Sends message and puts first reaction"""

        global message_id
        global current_reaction
        global needs_ride

        # Makes sure that is not triggered by its own message
        if message.author == client.user:
            return

        username: str = str(message.author)
        user_message: str = str(message.content)
        channel: str = str(message.channel)

        print(f"{username} said: '{user_message}' ({channel})")

        if user_message == "!test":

            test_list = ['brentond', 'joelle704', 'hungry1024']

            with open(LOCATIONS_PATH, 'r') as f:
                user_info = json.load(f)

            # location_groups: Dict[str, Set[discord.member.Member]] = dict()
            location_groups: Dict[str, str] = dict()


            # Fetch the message for which you want to get reactions
            # if message_id is None:
            #     await message.channel.send("Message has not sent yet.")
            #     return

            # target_message = await message.channel.fetch_message(message_id)

            # Iterate through reactions and collect users who reacted
            # reaction_users: Set[discord.member.Member] = set()
            # for reaction in target_message.reactions:
            for user in test_list:
                # async for user in reaction.users():
                if str(user) == BOT_NAME:
                    continue
                user_identifier: str = str(user)
                user_location: str = user_info[user_identifier]["location"]
                if user_location not in location_groups:
                    location_groups[user_location] = {user_identifier}
                else:
                    location_groups[user_location].add(user_identifier)

                    # reaction_users.add(user)

            # users_list = ", ".join(str(user) for user in reaction_users)
            for location in location_groups:
                users_at_location = ", ".join(str(user) for user in location_groups[location])
                await message.channel.send(f"{location}: {users_at_location}")
            

            return

            # role = ping.get_role(message.guild, 1188019586470256713)
            # await message.channel.send(f"{role.mention}")

            # return
            # for member in message.guild.members:
            #     print(member)
            # print("Test run")
            gaggle_user = discord.utils.get(message.guild.members, name='brentond')  # Change 'gaggle' to the actual username
            
            user = ping.get_member(message.guild.members, 'brentond')
            
            print(type(message.guild.members))
            if gaggle_user:
                await message.channel.send(f"{user.mention}, someone mentioned 'Gaggle'!")
            role = message.guild.get_role(1188019586470256713)
            await message.channel.send(f"{role.mention}")



        if user_message == "!help":
            await message.channel.send("""```
                                       !send - sends ride message \n
                                       !get_reactions - lists users who have reacted
                                       ```""")


        if user_message == "!send":
            # Clears list before each reaction
            needs_ride = []

            to_send: str = ping.create_message(ping.get_role(message.guild, ROLE_ID), RIDES_MESSAGE)
            sent_message: discord.message.Message = await message.channel.send(to_send)
            message_id = sent_message.id

            # Adds random reaction for ride
            current_reaction = random.randint(0, len(REACTS) - 1)
            await sent_message.add_reaction(REACTS[current_reaction])
            print(current_reaction)

        if message.content == "!get_reactions":
            # Fetch the message for which you want to get reactions
            if message_id is None:
                await message.channel.send("Message has not sent yet.")
                return

            target_message = await message.channel.fetch_message(message_id)

            # Iterate through reactions and collect users who reacted
            reaction_users: Set[discord.member.Member] = set()
            for reaction in target_message.reactions:
                async for user in reaction.users():
                    if str(user) == BOT_NAME:
                        continue
                    reaction_users.add(user)

            users_list = ", ".join(str(user) for user in reaction_users)
            await message.channel.send(f"Users who reacted: {users_list}")
        
        if message.content == "!ping":
            if message_id is None:
                await message.channel.send("Message has not sent yet.")
                return
            target_message = await message.channel.fetch_message(message_id)

            reaction_users = set()
            for reaction in target_message.reactions:
                async for user in reaction.users():
                    if str(user) == BOT_NAME:
                        continue
                    reaction_users.add(user)

            users_list = ", ".join(ping.get_member(message.guild.members, str(user)).mention for user in reaction_users)
            await message.channel.send(f"Users who reacted: {users_list}")


    client.run(TOKEN)