import discord
import os
from dotenv import load_dotenv
import random
import copy
load_dotenv()
TOKEN = os.getenv('TOKEN')
needs_ride = []
prev_needs_ride = []
drivers = []
reacts = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']
RIDES_MESSAGE: str = "React for rides."
current_reaction: int = 0
message_id = None

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
        global message_id
        global current_reaction
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
            prev_needs_ride = copy.deepcopy(needs_ride)
            needs_ride = []
            sent_message = await message.channel.send(RIDES_MESSAGE)
            message_id = sent_message.id
            # Adds random reaction for ride
            current_reaction = random.randint(0, len(reacts) - 1)
            await sent_message.add_reaction(reacts[current_reaction])
            print(current_reaction)

        
        if user_message == "!list":
            if len(needs_ride) == 0:
                await message.channel.send("List currently empty.")
            else:
                # needs_ride_username = ["@" + name for name in needs_ride]
                # await message.channel.send(", ".join(needs_ride_username))
                mentions = [f"<@{message.guild.get_member_named(name).id}>" for name in needs_ride]
                await message.channel.send(" ".join(mentions))

        if message.content == "!m_id":
            await message.channel.send(str(message_id))
        
        if message.content == "!get_reactions":
            # Fetch the message for which you want to get reactions
            if message_id == 0:
                await message.channel.send("Message has not sent yet.")
                return
            
            target_message = await message.channel.fetch_message(message_id)  # Replace message_id with the desired message ID

            # Iterate through reactions and collect users who reacted
            reaction_users = set()
            for reaction in target_message.reactions:
                async for user in reaction.users():
                    reaction_users.add(user)

            # Output the list of users who reacted
            users_list = ", ".join(str(user) for user in reaction_users)
            await message.channel.send(f"Users who reacted: {users_list}")
            # mentions = [f"<@{message.guild.get_member_named(name).id}>" for name in reaction_users]
            # await message.channel.send(" ".join(mentions))

    client.run(TOKEN)