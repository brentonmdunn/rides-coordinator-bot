"""Main functionality of bot"""

import copy
import json
import os
import random
from typing import Dict, List, Set

import discord
from dotenv import load_dotenv

import utils.ping as ping
from commands import group, help, send

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

with open(LOCATIONS_PATH, 'r', encoding='utf8') as f:
    user_info: Dict[str, Dict[str, str]] = json.load(f)
user_info_perm_changes = copy.deepcopy(user_info)

def run():

    intents: discord.Intents = discord.Intents.all()
    intents.message_content = True
    client: discord.Client = discord.Client(intents=intents)

    async def get_users_who_reacted(message) -> Set[discord.member.Member]:
        """Returns set of member objects of users who reacted."""
        target_message = await message.channel.fetch_message(message_id)

        # Iterate through reactions and collect users who reacted
        reaction_users: Set[discord.member.Member] = set()
        for reaction in target_message.reactions:
            async for user in reaction.users():
                if str(user) == BOT_NAME:
                    continue
                reaction_users.add(user)
        
        return reaction_users

    @client.event
    async def on_ready() -> None:
        """Prints on start"""
        print(f"{client.user} is running.")

    @client.event
    async def on_message(message: discord.message.Message) -> None:
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

        if user_message == "!group":
            await group.execute(message, message_id, BOT_NAME, user_info)
            # # Fetch the message for which you want to get reactions
            # if message_id is None:
            #     await message.channel.send("Message has not sent yet.")
            #     return
            
            # location_groups: Dict[str, Set[discord.member.Member]] = dict()
            # target_message = await message.channel.fetch_message(message_id)

            # reaction_users: Set[discord.member.Member] = await get_users_who_reacted(message)

            # for user in reaction_users:
            #     if str(user) == BOT_NAME:
            #         continue
            #     user_identifier: str = str(user)
            #     user_location: str = user_info[user_identifier]["location"]
            #     if user_location in location_groups:
            #         location_groups[user_location].add(user_identifier)
            #     else:
            #         location_groups[user_location] = {user_identifier}

            # for location, users in location_groups.items():
            #     users_at_location = ", ".join(user_info[user]['fname'] for user in users)
            #     await message.channel.send(f"{location}: {users_at_location}")


        if user_message == "!help":
            await help.execute(message)
            # await message.channel.send("""```
            #                            !send - sends ride message \n
            #                            !get_reactions - lists users who have reacted \n
            #                            !group - groups users by location
            #                            ```""")


        if user_message == "!send":

            message_id = await send.execute(message, needs_ride, RIDES_MESSAGE, REACTS, ROLE_ID)

            # # Clears list before each reaction
            # needs_ride = []

            # to_send: str = ping.create_message(ping.get_role(message.guild, ROLE_ID), RIDES_MESSAGE)
            # sent_message: discord.message.Message = await message.channel.send(to_send)
            # message_id = sent_message.id

            # # Adds random reaction for ride
            # current_reaction = random.randint(0, len(REACTS) - 1)
            # await sent_message.add_reaction(REACTS[current_reaction])
            # print(current_reaction)

        if message.content == "!get_reactions":
            # Fetch the message for which you want to get reactions
            if message_id is None:
                await message.channel.send("Message has not sent yet.")
                return

            reaction_users: Set[discord.member.Member] = await get_users_who_reacted(message)

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