"""Main functionality of bot"""

import copy
import json
import os
from typing import Dict, List

import discord
from dotenv import load_dotenv

from commands import group, help, send, get_reactions   # pylint: disable=W0622

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
    """Starts the bot"""

    intents: discord.Intents = discord.Intents.all()
    intents.message_content = True
    client: discord.Client = discord.Client(intents=intents)    

    @client.event
    async def on_ready() -> None:
        """Prints on start"""
        print(f"{client.user} is running.")

    @client.event
    async def on_message(message: discord.message.Message) -> None:
        """Sends message and puts first reaction"""

        global message_id           # pylint: disable=W0603
        global current_reaction     # pylint: disable=W0602
        global needs_ride           # pylint: disable=W0602

        # Makes sure that is not triggered by its own message
        if message.author == client.user:
            return

        username: str = str(message.author)
        user_message: str = str(message.content)
        channel: str = str(message.channel)

        print(f"{username} said: '{user_message}' ({channel})")

        if user_message == "!group":
            await group.execute(message, message_id, BOT_NAME, user_info)

        if user_message == "!help":
            await help.execute(message)
           
        if user_message == "!send":
            message_id = await send.execute(message, RIDES_MESSAGE, REACTS, ROLE_ID)

        if message.content == "!get_reactions":
            await get_reactions.execute(message, message_id, BOT_NAME)

        # if message.content == "!ping":
        #     await ping.execute(message, message_id, BOT_NAME)
            # if message_id is None:
            #     await message.channel.send("Message has not sent yet.")
            #     return
            # target_message = await message.channel.fetch_message(message_id)

            # reaction_users = set()
            # for reaction in target_message.reactions:
            #     async for user in reaction.users():
            #         if str(user) == BOT_NAME:
            #             continue
            #         reaction_users.add(user)

            # users_list = ", ".join(ping.get_member(message.guild.members, str(user)).mention for user in reaction_users)
            # await message.channel.send(f"Users who reacted: {users_list}")


    client.run(TOKEN)


if __name__ == "__main__":
    run()
