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
import utils.ping as ping
import utils.constants as constants

# Environment variables from .env file
load_dotenv()
TOKEN: str = os.getenv('TOKEN')
BOT_NAME: str = os.getenv('BOT_NAME')
LOCATIONS_PATH: str = os.getenv('LOCATIONS_PATH')

# Global variables
message_id: int = 0
channel_id: int = 0

with open(LOCATIONS_PATH, 'r', encoding='utf8') as f:
    user_info: Dict[str, Dict[str, str]] = json.load(f)
user_info_perm_changes = copy.deepcopy(user_info)


def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.all()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""

        # try:
        #     synced = await bot.tree.sync()
        #     print(f"{len(synced)} command(s).")
        # except Exception as e:      # pylint: disable=W0718
        #     print(e)

        print(f'Logged in as {bot.user.name}')


    async def send_message(interaction: discord.Interaction, message: str, ephemeral=False) -> None:
        """Simplifies sending messages."""
        await interaction.response.send_message(message, ephemeral=ephemeral)


    async def get_reaction_users() -> Set[discord.member.Member]:
        """
        Gets member objects of people who reacted to message.
        Assumption: Message has been sent and `message_id` and `channel_id` have values.
        """

        channel = bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)

        # Iterate through reactions and collect users who reacted
        reaction_users: Set[discord.member.Member] = set()

        # Loops through all reactions not just suggested one
        for reaction in message.reactions:
            async for user in reaction.users():
                if str(user) == BOT_NAME:
                    continue
                reaction_users.add(user)

        return reaction_users

    @bot.tree.command(name='help_rides', description=constants.HELP_DESCRIPTION)
    async def help_rides(interaction: discord.Interaction) -> None:   # pylint: disable=W0622
        """List of slash commands available."""

        embed = discord.Embed(color=discord.Color.purple())

        embed.add_field(name='/send', value=f'{constants.SEND_DESCRIPTION}')
        embed.add_field(name='/group', value=f'{constants.GROUP_DESCRIPTION}')
        embed.add_field(name='/_rideshelp', value=f'{constants.HELP_DESCRIPTION}')

        await interaction.response.send_message(embed=embed)

        # channel = await interaction.user.create_dm()
        # channel = bot.get_user(489147889117954059)
        # await channel.send("hello")


    @bot.tree.command(name='group', description=constants.GROUP_DESCRIPTION)
    async def group(interaction: discord.Interaction) -> None:
        """Groups people by pickup location."""

        if message_id == 0:
            await interaction.response.send_message("Message has not sent yet.")
            return

        location_groups: Dict[str, Set[discord.member.Member]] = dict()
        # Example:
        # {
        #     Sixth: { Person A, Person B }
        #     Seventh: { Person C }
        # }

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

        message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.ROLE_ID),
                                                                 constants.RIDES_MESSAGE)
        await interaction.response.send_message(message_to_send)

        message_obj: discord.InteractionMessage = await interaction.original_response()

        message_id = message_obj.id
        channel_id = message_obj.channel.id

        channel = bot.get_channel(channel_id)
        target_message = await channel.fetch_message(message_id)

        # Adds random reaction for ride
        current_reaction = random.randint(0, len(constants.REACTS) - 1)
        await target_message.add_reaction(constants.REACTS[current_reaction])


    async def handle_is_authorized(interaction: discord.Interaction, user: str) -> bool:
        """Checks if user is authorized to use admin commands."""
        if not user in constants.AUTHORIZED_ADMIN:
            await send_message(interaction, "Not authorized to use command.")
            return False
        return True


    @bot.tree.command(name='admin_list_user_info', description=constants.ADMIN_LIST_USER_INFO_DESCRIPTION)
    @app_commands.describe(user='Specific user')
    async def admin_list_user_info(interaction: discord.Interaction, user:str=None) -> None:
        """Gets all user info or a named user (optional param)."""

        is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
        if not is_authorized:
            return

        # Sends all info
        if user is None:
            await send_message(interaction, json.dumps(user_info, indent=4), True)
            return

        # User not found
        if user not in user_info:
            await send_message(interaction, "User not found.", True)
            return

        # Found user, sends info
        await send_message(interaction, f"```json\n{json.dumps(user_info[user], indent=4)}", True)


    @bot.tree.command(name='admin_get_rxn_users', description=constants.ADMIN_GET_REACTION_USERS_DESCRIPTION)
    async def admin_get_rxn_users(interaction: discord.Interaction) -> None:
        """Get list of users who reacted to message."""

        is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
        if not is_authorized:
            return

        set_member_obj: Set[discord.member.Member] = await get_reaction_users()
        list_member_str: List[str] = [str(user) for user in set_member_obj]
        user_str: str = ', '.join(list_member_str)
        await send_message(interaction, user_str)


    @bot.tree.command(name='admin_help', description=constants.ADMIN_HELP_DESCRIPTION)
    async def admin_help(interaction: discord.Interaction) -> None:
        """Slash commands available for admins."""

        is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
        if not is_authorized:
            return

        embed = discord.Embed(color=discord.Color.purple())

        embed.add_field(name='/admin_get_rxn_users',
                        value=f'{constants.ADMIN_GET_REACTION_USERS_DESCRIPTION}')
        embed.add_field(name='/admin_list_user_info',
                        value=f'{constants.ADMIN_LIST_USER_INFO_DESCRIPTION}')
        embed.add_field(name='/admin_help',
                        value=f'{constants.ADMIN_HELP_DESCRIPTION}')

        await interaction.response.send_message(embed=embed)

    
    @bot.tree.command(name='sync_commands', description="Syncs slash commands with server")
    async def sync_commands(interaction: discord.Interaction) -> None:
        is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
        if not is_authorized:
            return
        
        try:
            print("Executed")
            synced = await bot.tree.sync()
            print(f"{len(synced)} command(s).")
            await send_message(interaction, f"{len(synced)} command(s) successfully synced.")
        except Exception as e:      # pylint: disable=W0718
            print(e)
        




    bot.run(TOKEN)


if __name__ == "__main__":
    run()
