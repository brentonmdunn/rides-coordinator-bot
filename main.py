# import discord
# from discord.ext import commands

# import os
# from dotenv import load_dotenv

# load_dotenv()
# TOKEN = os.getenv('TOKEN')

# intents = discord.Intents.default()
# intents.messages = True
# intents.guilds = True

# bot = commands.Bot(command_prefix='!', intents=intents)

# @bot.event
# async def on_ready():
#     await bot.load_extension(cmds.hello) #this is only an example
# #if file is in another folder, do this: 
# #(example.hello), hello being your extension name, and example the folder name.
#     await bot.sync() #syncs command tree
# #anything after it
# #     try:
# #         synced = await bot.tree.sync()
# #         print(f"{len(synced)} command(s).")
# #     except Exception as e:
# #         print(e)

# #     print(f'Logged in as {bot.user.name}')

# # # Load commands
# # initial_extensions = [
# #     'commands.hello',
# #     'commands.say',
# #     # Add more commands if you have them in the future
# # ]

# # if __name__ == '__main__':
# #     for extension in initial_extensions:
# #         bot.load_extension(extension)

# bot.run(TOKEN)



# -----

"""Main functionality of bot"""

# Built in modules
import copy
import json
import os
import random
from typing import Dict, List, Set

# External modules
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Local modules
from cmds import group, help, send, get_reactions   # pylint: disable=W0622
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

message_id: int = None
channel_id: int = None

with open(LOCATIONS_PATH, 'r', encoding='utf8') as f:
    user_info: Dict[str, Dict[str, str]] = json.load(f)
user_info_perm_changes = copy.deepcopy(user_info)

def run() -> None:

    # global message_id           # pylint: disable=W0603


    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        try:
            synced = await bot.tree.sync()
            print(f"{len(synced)} command(s).")
        except Exception as e:
            print(e)

        print(f'Logged in as {bot.user.name}')

    async def get_reaction_users():
        # target_message = await message.channel.fetch_message(message_id)
        channel = bot.get_channel(channel_id)  # Replace YOUR_CHANNEL_ID with the channel ID
        message = await channel.fetch_message(message_id)

        # Iterate through reactions and collect users who reacted
        reaction_users: Set[discord.member.Member] = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if str(user) == BOT_NAME:
                    continue
                reaction_users.add(user)

        return reaction_users


    @bot.tree.command(name='group', description='Groups people in the same location.')
    async def group(interaction: discord.Interaction) -> None:
        # await group.execute(interaction, message_id, BOT_NAME, user_info)
        # Fetch the message for which you want to get reactions
        if message_id is None:
            await interaction.response.send_message("Message has not sent yet.")
            return

        location_groups: Dict[str, Set[discord.member.Member]] = dict()

        reaction_users: Set[discord.member.Member] = await get_reaction_users()
        for user in reaction_users:
            if str(user) == BOT_NAME:
                continue
            user_identifier: str = str(user)
            user_location: str = user_info[user_identifier]["location"]
            if user_location in location_groups:
                location_groups[user_location].add(user_identifier)
            else:
                location_groups[user_location] = {user_identifier}

        for location, users in location_groups.items():
            users_at_location = ", ".join(user_info[user]['fname'] for user in users)
            await interaction.response.send_message(f"{location}: {users_at_location}")

    @bot.tree.command(name='send', description='Sends rides message.')
    async def send(interaction: discord.Interaction):
        global message_id
        global channel_id

        to_send: str = ping.create_message(ping.get_role(interaction.guild, ROLE_ID), RIDES_MESSAGE)

        await interaction.response.send_message(to_send)

        message: discord.InteractionMessage = await interaction.original_response()

        message_id = message.id
        channel_id = message.channel.id

        channel = bot.get_channel(channel_id)
        target_message = await channel.fetch_message(message_id)

        # Adds random reaction for ride
        current_reaction = random.randint(0, len(REACTS) - 1)
        await target_message.add_reaction(REACTS[current_reaction])


    @bot.tree.command(name='hello', description="this is a test command")
    async def hello(interaction):
        await interaction.response.send_message("Slash command")

    @bot.tree.command(name='say', description='says hello')
    @app_commands.describe(thing_to_say = "What should I say?", second_param = "second")
    async def say(interaction: discord.Interaction, thing_to_say: str, second_param: str = 'default'):
        await interaction.response.send_message(f"{interaction.user.name} said: `{thing_to_say}`, second param: {second_param}")

    bot.run(TOKEN)



# -------------
# """Main functionality of bot"""

# # Built in modules
# import copy
# import json
# import os
# from typing import Dict, List

# # External modules
# import discord
# from discord.ext import commands
# from dotenv import load_dotenv

# # Local modules
# from commands import group, help, send, get_reactions   # pylint: disable=W0622

# # Environment variables from .env file
# load_dotenv()
# TOKEN = os.getenv('TOKEN')
# BOT_NAME = os.getenv('BOT_NAME')

# # Constants
# RIDES_MESSAGE: str = "React for rides."
# REACTS: List[str] = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']
# ROLE_ID: int = 1188019586470256713
# LOCATIONS_PATH = "locations.json"

# # Global variables
# message_id: int = None

# with open(LOCATIONS_PATH, 'r', encoding='utf8') as f:
#     user_info: Dict[str, Dict[str, str]] = json.load(f)
# user_info_perm_changes = copy.deepcopy(user_info)

# def run():
#     """Starts the bot"""

#     intents: discord.Intents = discord.Intents.all()
#     intents.message_content = True
#     bot = commands.Bot(command_prefix='!', intents=intents)

#     @bot.event
#     async def on_ready() -> None:
#         """Prints on start"""
#         await bot.tree.sync()
#         print(f"{bot.user} is running.")
        

#     @bot.command()
#     async def hello(ctx):
#         await ctx.send('Hello!')

#     @bot.tree.command(name="mannu",description="Mannu is a good boy")
#     async def slash_command(interaction:discord.Interaction):
#         await interaction.response.send_message("Hello World!")

#     bot.run(TOKEN)

    # -------------


    # intents: discord.Intents = discord.Intents.all()
    # intents.message_content = True
    # client: discord.Client = discord.Client(intents=intents)

    # @client.event
    # async def on_ready() -> None:
    #     """Prints on start"""
    #     print(f"{client.user} is running.")

    # @client.event
    # async def on_message(message: discord.message.Message) -> None:
    #     """Sends message and puts first reaction"""

    #     global message_id           # pylint: disable=W0603

    #     # Makes sure that is not triggered by its own message
    #     if message.author == client.user:
    #         return

    #     username: str = str(message.author)
    #     user_message: str = str(message.content)
    #     channel: str = str(message.channel)

    #     print(f"{username} said: '{user_message}' ({channel})")

    #     if user_message == "!group":
    #         await group.execute(message, message_id, BOT_NAME, user_info)

    #     if user_message == "!help":
    #         await help.execute(message)
           
    #     if user_message == "!send":
    #         message_id = await send.execute(message, RIDES_MESSAGE, REACTS, ROLE_ID)

    #     if message.content == "!get_reactions":
    #         await get_reactions.execute(message, message_id, BOT_NAME)

    # client.run(TOKEN)


if __name__ == "__main__":
    run()
