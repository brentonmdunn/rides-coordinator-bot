"""Main functionality of bot"""

import os
import random
from typing import List

import discord
from dotenv import load_dotenv

# Environment variables from .env file
load_dotenv()
TOKEN = os.getenv('TOKEN')
BOT_NAME = os.getenv('BOT_NAME')
GUILD_ID = os.getenv('GUILD_ID')

# Constants
RIDES_MESSAGE: str = "React for rides."
REACTS: List[str] = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']

# Global variables
needs_ride: List[str] = []
drivers: List[str] = []
current_reaction: int = 0
message_id = None

def run():

    intents: discord.Intents = discord.Intents.default()
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

        if user_message == "!help":
            await message.channel.send("```!send - sends ride message \n!get_reactions - lists users who have reacted```")

        if user_message == "!send":
            # Clears list before each reaction
            needs_ride = []

            sent_message = await message.channel.send(RIDES_MESSAGE)
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
            reaction_users = set()
            for reaction in target_message.reactions:
                async for user in reaction.users():
                    if str(user) == BOT_NAME:
                        continue
                    reaction_users.add(user)

            users_list = ", ".join(str(user) for user in reaction_users)
            await message.channel.send(f"Users who reacted: {users_list}")

    client.run(TOKEN)