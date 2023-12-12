import discord
import os
from dotenv import load_dotenv
import random

load_dotenv()
TOKEN = os.getenv('TOKEN')
needs_ride = []
drivers = []
reacts = ['🥐', '🧁', '🍩']
RIDES_MESSAGE: str = "React for rides."
current_reaction: int = 0

def run():
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        """Prints on start"""
        print(f"{client.user} is running.")

    @client.event
    async def on_message(message):
        """Sends message and puts first reaction"""

        # Makes sure that is not triggered by its own message
        if message.author == client.user:
            return 
        
        username: str = str(message.author)
        user_message: str = str(message.content)
        channel: str = str(message.channel)

        print(f"{username} said: '{user_message}' ({channel})")

        if user_message == "!send":
            message_id = await message.channel.send(RIDES_MESSAGE)

            # Adds random reaction for ride
            current_reaction = random.randint(0, len(reacts) - 1)
            await message_id.add_reaction(reacts[current_reaction])
            print(current_reaction)
        
        if user_message == "!list":
            await message.channel.send(", ".join(needs_ride))

    @client.event
    async def on_reaction_add(reaction, user):
        """Adds Discord username to list of users who need a ride"""

        if user.bot:
            return

        if str(reaction.emoji) == reacts[current_reaction] and reaction.message.author == client.user:
            await reaction.message.channel.send(f"Yay emoji reaction by {user.name}!")
            needs_ride.append(user.name)
            print(needs_ride)


    client.run(TOKEN)