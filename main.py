"""Main functionality of bot"""

# Built in modules
import copy
import json
import os
import random
from typing import Dict, Set

# External modules
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Local modules
import utils.ping as ping
import utils.constants as constants

# Environment variables from .env file
load_dotenv()
TOKEN: str = os.getenv('TOKEN')
BOT_NAME: str = os.getenv('BOT_NAME')

# Global variables
message_id: int = 0
channel_id: int = 0

with open(constants.LOCATIONS_PATH, 'r', encoding='utf8') as f:
    user_info: Dict[str, Dict[str, str]] = json.load(f)
user_info_perm_changes = copy.deepcopy(user_info)

def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.default()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""
        try:
            synced = await bot.tree.sync()
            print(f"{len(synced)} command(s).")
        except Exception as e:
            print(e)

        print(f'Logged in as {bot.user.name}')

    async def get_reaction_users() -> Set[discord.member.Member]:
        """Gets member objects of people who reacted to message."""

        channel = bot.get_channel(channel_id) 
        message = await channel.fetch_message(message_id)

        # Iterate through reactions and collect users who reacted
        reaction_users: Set[discord.member.Member] = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if str(user) == BOT_NAME:
                    continue
                reaction_users.add(user)

        return reaction_users

    @bot.tree.command(name='help', description=constants.HELP_DECRIPTION)
    async def help(interaction: discord.Interaction) -> None:
        """List of slash commands available."""

        command_list = (
            "/send - {constants.SEND_DESCRIPTION}"
            "\n/group - {constants.GROUP_DESCRIPTION}"
            "\n/help - {constants.HELP_DESCRIPTION}"
        )
        await interaction.response.send_message(f"```{command_list}```")

    @bot.tree.command(name='group', description=constants.GROUP_DESCRIPTION)
    async def group(interaction: discord.Interaction) -> None:
        """Groups people by pickup location."""

        if message_id == 0:
            await interaction.response.send_message("Message has not sent yet.")
            return

        location_groups: Dict[str, Set[discord.member.Member]] = dict()

        reaction_users: Set[discord.member.Member] = await get_reaction_users()
        for user in reaction_users:
            if str(user) == BOT_NAME:
                continue
            user_identifier: str = str(user)
            user_location: str = user_info[user_identifier]["location"]

            # Adds user to set if location exists, else creates set
            if user_location in location_groups:
                location_groups[user_location].add(user_identifier)
            else:
                location_groups[user_location] = {user_identifier}

        for location, users in location_groups.items():
            users_at_location = ", ".join(user_info[user]['fname'] for user in users)
            await interaction.response.send_message(f"{location}: {users_at_location}")

    @bot.tree.command(name='send', description=constants.SEND_DESCRIPTION)
    async def send(interaction: discord.Interaction) -> None:
        """Sends the message for people to react to for rides."""

        global message_id   # pylint: disable=W0603
        global channel_id   # pylint: disable=W0603

        message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.ROLE_ID), constants.RIDES_MESSAGE)
        await interaction.response.send_message(message_to_send)

        message_obj: discord.InteractionMessage = await interaction.original_response()

        message_id = message_obj.id
        channel_id = message_obj.channel.id

        channel = bot.get_channel(channel_id)
        target_message = await channel.fetch_message(message_id)

        # Adds random reaction for ride
        current_reaction = random.randint(0, len(constants.REACTS) - 1)
        await target_message.add_reaction(constants.REACTS[current_reaction])


    # Sample slash command with params
    # @bot.tree.command(name='say', description='says hello')
    # @app_commands.describe(thing_to_say = "What should I say?", second_param = "second")
    # async def say(interaction: discord.Interaction, thing_to_say: str, second_param: str = 'default'):
    #     await interaction.response.send_message(f"{interaction.user.name} said: `{thing_to_say}`, second param: {second_param}")

    bot.run(TOKEN)


if __name__ == "__main__":
    run()
