"""Main functionality of bot"""

import asyncio
import schedule
from discord.ext import commands, tasks

# Built in modules
import copy
import json
import os
from typing import Dict, List, Set, Union
import random

# External modules
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import yaml

# Local modules
from logger import logger
import utils.ping as ping
import utils.constants as constants

# Environment variables from .env file
load_dotenv()
TOKEN: str = os.getenv('TOKEN')
BOT_NAME: str = os.getenv('BOT_NAME')
LOCATIONS_PATH: str = os.getenv('LOCATIONS_PATH')
EMERGENCY_CONTACT: int = int(os.getenv('EMERGENCY_CONTACT'))
GUILD_ID: int = int(os.getenv('GUILD_ID'))

# Constants
SETTINGS_PATH = 'settings/settings.yaml'

# Global variables
message_id: int = 0
channel_id: int = 0
new_message = ""

# with open(LOCATIONS_PATH, 'r', encoding='utf8') as f:
#     all_info: Dict[str, Union[int, Dict[str, str]]] = json.load(f)
#     drivers: List[List[str]] = all_info['drivers']
#     user_info: Dict[str, Dict[str, str]] = all_info['locations']
# user_info_perm_changes = copy.deepcopy(user_info)

with open(SETTINGS_PATH, 'r', encoding='utf8') as f:
    settings = yaml.safe_load(f)


# def reset_settings():
    


def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.all()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)


    # async def _send() -> None:
    #     """Sends the message for people to react to for rides."""

    #     # logger.info("_send command was executed")

    #     # bots channel
    #     # channel = bot.get_channel(916823070017204274)

    #     # ACTUAL RIDES CHANNEL
    #     channel = bot.get_channel(939950319721406464)

    #     _guild = bot.get_guild(GUILD_ID)
    #     message_to_send: str = ping.create_message(ping.get_role(_guild, constants.ROLE_ID),
    #                                                              constants.RIDES_MESSAGE1)
    #     # message_to_send = "hello!!"
    #     await channel.send(message_to_send)
    #     logger.info("_send concluded")
    #     # await interaction.response.send_message("Message sent!")
    
    # async def backup_settings() -> None:
    #     logger.info("Backup initiated")
    #     channel = bot.get_channel(constants.BOTS_SETTINGS_BACKUP_CHANNEL_ID)
    #     _guild = bot.get_guild(GUILD_ID)
    #     await channel.send(f"```\n{json.dumps(settings, indent=2)}\n```")
    #     logger.info("Backup successful")

    # async def send_logs(log) -> None:
    #     channel = bot.get_channel(constants.BOT_LOGS_CHANNEL_ID)
    #     await channel.send(log)
        


      

    # @tasks.loop(minutes=1)
    # async def scheduler():
    #     schedule.run_pending()

    # @bot.event
    # async def on_ready():
    #     scheduler.start()
    #     logger.debug("Scheduler started")

    # # schedule.every().thursday.at(
    # #     settings['friday_notif_time_modified'] 
    # #     if settings['friday_notif_time_modified'] != "" 
    # #     else settings['friday_notif_time_default']
    # # ).do(asyncio.create_task, _send())

    # # schedule.every().friday.at(
    # #     settings['sunday_notif_time_modified'] 
    # #     if settings['sunday_notif_time_modified'] != "" 
    # #     else settings['sunday_notif_time_default']
    # # ).do(asyncio.create_task, _send())

    # schedule.every().day.at("10:30").do(asyncio.create_task, backup_settings())
    # logger.info("Backup scheduled")
    
    # # logger.debug("Line after scheduler line")

    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s).")
        except Exception as e:      # pylint: disable=W0718
            print(e)

    # #     logger.debug("on_ready began")
    # #     threading.Thread(target=run_scheduler).start()

    # #     logger.info(f'Logged in as {bot.user.name}')
    # #     # print(f'Logged in as {bot.user.name}')
    # @bot.tree.command(name='display_settings', description=constants.HELP_DESCRIPTION)
    # async def display_settings(interaction: discord.Interaction) -> None:
    #     logger.info("Backup initiated")
    #     channel = bot.get_channel(constants.BOTS_SETTINGS_BACKUP_CHANNEL_ID)
    #     _guild = bot.get_guild(GUILD_ID)
    #     await channel.send(f"```\n{json.dumps(settings, indent=2)}\n```")
    #     logger.info("Backup successful")
    #     await send_message(interaction, """Successful""", True)

    # @bot.tree.command(name='load_settings', description=constants.HELP_DESCRIPTION)
    # @app_commands.describe(json_str='JSON text of settings')
    # async def load_settings(interaction: discord.Interaction, json_str: str) -> None:
    #     logger.info("Settings load initiated")

    #     global settings
    #     settings = json.loads(json_str)

    #     channel = bot.get_channel(constants.BOTS_SETTINGS_BACKUP_CHANNEL_ID)
    #     await channel.send(f"```\n{json.dumps(settings, indent=2)}\n```")
    #     logger.info("Settings load successful")
    #     await send_message(interaction, """Successful""", True)

    # def is_friday_or_sunday(day):
    #     if day.lower().strip() == "sunday" or day.lower().strip() == "friday":
    #         return True
    #     return False

    # def is_valid_time(time: str) -> bool:
    #     if len(time) != 4 and len(time) != 5:
    #         return False
            
    #     if len(time) == 4:
    #         h1, colon, m1, m2 = time
    #         try:
    #             if not (
    #                 int(h1) in list(range(10)) and
    #                 colon in list(":") and
    #                 int(m1) in list(range(6)) and
    #                 int(m2) in list(range(10))
    #             ):
    #                 logger.debug("false1")
    #                 return False
    #         except ValueError:
    #             logger.debug("false2")
    #             return False
    #     else:
    #         h1, h2, colon, m1, m2 = time
    #         try:
    #             if not (
    #                 int(h1) in list(range(10)) and
    #                 int(h2) in list(range(3)) and
    #                 colon in list(":") and
    #                 int(m1) in list(range(6)) and
    #                 int(m2) in list(range(10))
    #             ):
    #                 return False
    #         except ValueError:
    #             return False
    #     return True

    # @bot.tree.command(name='list_messages', description=constants.HELP_DESCRIPTION)
    # @app_commands.describe(day='Which day to list')
    # async def list_messages(interaction: discord.Interaction, day: str) -> None:

    #     full_message = ""
    #     count = 0
    #     if not is_friday_or_sunday(day):
    #         await send_message(interaction, """Please write either "Friday" or "Sunday" into parameter field""", True)
    #         return
    #     if day.lower() == "friday":
    #         for idx, message in enumerate(settings['modified']['messages']['friday_message_modified']):
    #             count += 1
    #             time = settings['modified']['leave_times']['friday_leave_time_modified'][idx]
    #             full_message += f"{count:<2} | {time:<6} | {message:<20}\n"

    #         full_message = f"```{full_message}```"
    #         await send_message(interaction, full_message)
    #     else:
    #         for idx, message in enumerate(settings['modified']['messages']['sunday_message_modified']):
    #             count += 1
    #             time = settings['modified']['leave_times']['sunday_leave_time_modified'][idx]
    #             full_message += f"{count:<2} | {time:<6} | {message:<20}\n"

    #         full_message = f"```{full_message}```"
    #         await send_message(interaction, full_message)

    # @bot.tree.command(name='delete_message', description=constants.HELP_DESCRIPTION)
    # @app_commands.describe(day='Which day to list', number='Which number message to delete')
    # async def delete_message(interaction: discord.Interaction, day: str, number: str) -> None:

    #     if not number.strip().isdigit():
    #         await send_message(interaction, "Write a valid number. Numbers can be found with `\list_messages`.", True)
    #         return
        
    #     if not is_friday_or_sunday(day):
    #         await send_message(interaction, """Please write either "Friday" or "Sunday" into parameter field""", True)
    #         return

    #     if day.lower() == "friday":
    #         deleted_message = settings['modified']['messages']['friday_message_modified'].pop(int(number)-1)
    #         deleted_leave_time = settings['modified']['leave_times']['friday_leave_time_modified'].pop(int(number)-1)
    #     else:
    #         deleted_message = settings['modified']['messages']['sunday_message_modified'].pop(int(number)-1)
    #         deleted_leave_time = settings['modified']['leave_times']['sunday_leave_time_modified'].pop(int(number)-1)

    #     await send_message(interaction, f"Deleted the following message: {deleted_message}")



    # @bot.tree.command(name='add_message', description=constants.HELP_DESCRIPTION)
    # @app_commands.describe(day='Which day to edit', message='New message', time_to_leave='Departure time (in military time)')
    # async def add_message(interaction: discord.Interaction, day: str, message: str, time_to_leave: str) -> None:   # pylint: disable=W0622
    #     # await send_message(interaction, """Please note that if you do not already have a modified message, this overrides the default message.""", True)
    #     if not is_friday_or_sunday(day):
    #         await send_message(interaction, """Please write either "Friday" or "Sunday" into parameter field""", True)
    #         return
        
    #     if not is_valid_time(time_to_leave):
    #         await send_message(interaction, """Please write a valid time""", True)
    #         return
        
    #     if day.lower() == "friday":
    #         settings['modified']['messages']['friday_message_modified'].append(message)
    #         settings['modified']['leave_times']['friday_leave_time_modified'].append(time_to_leave)
    #     else:
    #         settings['modified']['messages']['sunday_message_modified'].append(message)
    #         settings['modified']['leave_times']['sunday_leave_time_modified'].append(time_to_leave)

    #     await backup_settings()
    #     await send_message(interaction, """Successful""", True)
        

    # @bot.tree.command(name='change_notif_time', description=constants.HELP_DESCRIPTION)
    # @app_commands.describe(day='Which day to edit', time='Time to change to in military time')
    # async def change_notif_time(interaction: discord.Interaction, day: str, time: str) -> None:   # pylint: disable=W0622

    #     if not is_friday_or_sunday(day):
    #         await send_message(interaction, """Please write either "Friday" or "Sunday" into parameter field""", True)
    #         return

    #     if not is_valid_time(time):
    #         await send_message(interaction, """Please write a valid time""", True)
    #         return


    #     if day.lower() == "friday":
    #         settings['modified']['notif_times']['friday_notif_time_modified'] = time
    #     else:
    #         settings['modified']['notif_times']['sunday_notif_time_modified'] = time

    #     await backup_settings()
    #     await send_message(interaction, """Successful""", True)




    # async def send_message(interaction: discord.Interaction, message: str, ephemeral=False) -> None:
    #     """Simplifies sending messages."""
    #     await interaction.response.send_message(message, ephemeral=ephemeral)


    # async def get_reaction_users() -> Set[discord.member.Member]:
    #     """
    #     Gets member objects of people who reacted to message.
    #     Assumption: Message has been sent and `message_id` and `channel_id` have values.
    #     """

    #     channel = bot.get_channel(channel_id)
    #     message = await channel.fetch_message(message_id)

    #     # Iterate through reactions and collect users who reacted
    #     reaction_users: Set[discord.member.Member] = set()

    #     # Loops through all reactions not just suggested one
    #     for reaction in message.reactions:
    #         async for user in reaction.users():
    #             if str(user) == BOT_NAME:
    #                 continue
    #             reaction_users.add(user)

    #     return reaction_users
    
    # async def send_dm(interaction: discord.Interaction, user_id: int, message: str) -> None:
    #     """
    #     Sends DM to user.

    #     Args:
    #         interaction: Discord interaction object
    #         user_id: ID of Discord user
    #         message: Message to send in DM
    #     """
    #     channel = await interaction.user.create_dm()
    #     channel = bot.get_user(user_id)
    #     await channel.send(message)

    # @bot.tree.command(name='help_rides', description=constants.HELP_DESCRIPTION)
    # async def help_rides(interaction: discord.Interaction) -> None:   # pylint: disable=W0622
    #     """List of slash commands available."""

    #     embed = discord.Embed(color=discord.Color.purple())

    #     embed.add_field(name='/send', value=f'{constants.SEND_DESCRIPTION}')
    #     embed.add_field(name='/group', value=f'{constants.GROUP_DESCRIPTION}')
    #     embed.add_field(name='/rides_help', value=f'{constants.HELP_DESCRIPTION}')

    #     await interaction.response.send_message(embed=embed)

        
    # async def group_helper(interaction: discord.Interaction) -> Dict[str, Set[discord.member.Member]]:
    #     location_groups: Dict[str, Set[discord.member.Member]] = dict()
    #     # Example:
    #     # {
    #     #     Sixth: { Person A, Person B }
    #     #     Seventh: { Person C }
    #     # }

    #     reaction_users: Set[discord.member.Member] = await get_reaction_users()
    #     for user in reaction_users:
    #         if str(user) == BOT_NAME:
    #             continue
    #         if user not in user_info:
    #             message = f"{user} is not in locations.json file."
    #             await send_dm(interaction, EMERGENCY_CONTACT, message)
    #         user_identifier: str = str(user)
    #         user_location: str = user_info[user_identifier]["location"]

    #         # Adds user to set if location exists, else creates set
    #         if user_location in location_groups:
    #             location_groups[user_location].add(user_identifier)
    #         else:
    #             location_groups[user_location] = {user_identifier}
    #     return location_groups


    # @bot.tree.command(name='group', description=constants.GROUP_DESCRIPTION)
    # async def group(interaction: discord.Interaction) -> None:
    #     """Groups people by pickup location."""

    #     if message_id == 0:
    #         await interaction.response.send_message("Message has not sent yet.")
    #         return

    #     location_groups = await group_helper(interaction)
    #     # location_groups: Dict[str, Set[discord.member.Member]] = dict()
    #     # # Example:
    #     # # {
    #     # #     Sixth: { Person A, Person B }
    #     # #     Seventh: { Person C }
    #     # # }

    #     # reaction_users: Set[discord.member.Member] = await get_reaction_users()
    #     # for user in reaction_users:
    #     #     if str(user) == BOT_NAME:
    #     #         continue
    #     #     if user not in user_info:
    #     #         message = f"{user} is not in locations.json file."
    #     #         await send_dm(interaction, EMERGENCY_CONTACT, message)
    #     #     user_identifier: str = str(user)
    #     #     user_location: str = user_info[user_identifier]["location"]

    #     #     # Adds user to set if location exists, else creates set
    #     #     if user_location in location_groups:
    #     #         location_groups[user_location].add(user_identifier)
    #     #     else:
    #     #         location_groups[user_location] = {user_identifier}

    #     for location, users in location_groups.items():
    #         users_at_location = ", ".join(user_info[user]['fname'] for user in users)
    #         await interaction.response.send_message(f"{location}: {users_at_location}")


    # @bot.tree.command(name='send', description=constants.SEND_DESCRIPTION)
    # # async def send(interaction: discord.Interaction) -> None:
    # async def send(interaction: discord.Interaction) -> None:

    #     """Sends the message for people to react to for rides."""

    #     logger.info("Send command was executed")

    #     channel = bot.get_channel(916823070017204274)
    #     message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.ROLE_ID),
    #                                                              constants.RIDES_MESSAGE)
    #     await channel.send(message_to_send)
    #     await interaction.response.send_message("Message sent!")

    #     # global message_id   # pylint: disable=W0603
    #     # global channel_id   # pylint: disable=W0603

    #     # channel_id = 916823070017204274


    #     # message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.ROLE_ID),
    #     #                                                          constants.RIDES_MESSAGE)
    #     # await interaction.response.send_message(message_to_send)

    #     # message_obj: discord.InteractionMessage = await interaction.original_response()

    #     # message_id = message_obj.id
    #     # channel_id = message_obj.channel.id

    #     # logger.debug(channel_id)

    #     # channel = bot.get_channel(channel_id)

    #     # --
    #     # target_message = await channel.fetch_message(message_id)

    #     # Adds random reaction for ride
    #     # current_reaction = random.randint(0, len(constants.REACTS) - 1)
    #     # await target_message.add_reaction(constants.REACTS[current_reaction])


    # async def handle_is_authorized(interaction: discord.Interaction, user: str) -> bool:
    #     """Checks if user is authorized to use admin commands."""
    #     if not user in constants.AUTHORIZED_ADMIN:
    #         await send_message(interaction, "Not authorized to use command.")
    #         return False
    #     return True


    # @bot.tree.command(name='admin_list_user_info', description=constants.ADMIN_LIST_USER_INFO_DESCRIPTION)
    # @app_commands.describe(user='Specific user')
    # async def admin_list_user_info(interaction: discord.Interaction, user:str=None) -> None:
    #     """Gets all user info or a named user (optional param)."""

    #     is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
    #     if not is_authorized:
    #         return

    #     # Sends all info
    #     if user is None:
    #         await send_message(interaction, json.dumps(user_info, indent=4), True)
    #         return

    #     # User not found
    #     if user not in user_info:
    #         await send_message(interaction, "User not found.", True)
    #         return

    #     # Found user, sends info
    #     await send_message(interaction, f"```json\n{json.dumps(user_info[user], indent=4)}", True)


    # @bot.tree.command(name='admin_get_rxn_users', description=constants.ADMIN_GET_REACTION_USERS_DESCRIPTION)
    # async def admin_get_rxn_users(interaction: discord.Interaction) -> None:
    #     """Get list of users who reacted to message."""

    #     is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
    #     if not is_authorized:
    #         return

    #     set_member_obj: Set[discord.member.Member] = await get_reaction_users()
    #     list_member_str: List[str] = [str(user) for user in set_member_obj]
    #     user_str: str = ', '.join(list_member_str)
    #     await send_message(interaction, user_str)


    # @bot.tree.command(name='admin_help', description=constants.ADMIN_HELP_DESCRIPTION)
    # async def admin_help(interaction: discord.Interaction) -> None:
    #     """Slash commands available for admins."""

    #     is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
    #     if not is_authorized:
    #         return

    #     embed = discord.Embed(color=discord.Color.purple())

    #     embed.add_field(name='/admin_get_rxn_users',
    #                     value=f'{constants.ADMIN_GET_REACTION_USERS_DESCRIPTION}')
    #     embed.add_field(name='/admin_list_user_info',
    #                     value=f'{constants.ADMIN_LIST_USER_INFO_DESCRIPTION}')
    #     embed.add_field(name='/admin_help',
    #                     value=f'{constants.ADMIN_HELP_DESCRIPTION}')

    #     await interaction.response.send_message(embed=embed)


    # @bot.tree.command(name='sync_commands', description="Syncs slash commands with server")
    # async def sync_commands(interaction: discord.Interaction) -> None:
    #     is_authorized: bool = await handle_is_authorized(interaction, str(interaction.user))
    #     if not is_authorized:
    #         return

    #     try:
    #         print("Executed")
    #         synced = await bot.tree.sync()
    #         print(f"{len(synced)} command(s).")
    #         await send_message(interaction, f"{len(synced)} command(s) successfully synced.")
    #     except Exception as e:      # pylint: disable=W0718
    #         print(e)


    # @bot.tree.command(name='assign', description='Assigns drivers to riders')
    # async def assign(interaction: discord.Interaction) -> None:

    #     location_groups: Dict[str, Set[discord.member.Member]] = await group_helper(interaction)
    #     # Example:
    #     # {
    #     #     Sixth: [ Person A, Person B ]
    #     #     Seventh: [ Person C ]
    #     # }

    #     num_on_campus = 0
    #     for location in location_groups:
    #         if location in constants.CAMPUS:
    #             num_on_campus += len(location_groups[location])

    #     # for i, drivers in enumerate(drivers):
    #     #     if i >= 

    @bot.tree.command(name="ask-drivers", description="Pings drivers to see who is available")
    async def ask_drivers(interaction: discord.Interaction, message: str) -> None:
        # embed = discord.Embed(color=discord.Color.purple())

        # embed.add_field(name='/send', value=f'{constants.SEND_DESCRIPTION}')
        # embed.add_field(name='/group', value=f'{constants.GROUP_DESCRIPTION}')
        # embed.add_field(name='/rides_help', value=f'{constants.HELP_DESCRIPTION}')
        # embed.add_field(name=f"{message}", value=f'{constants.HELP_DESCRIPTION}')

        # await interaction.response.send_message(embed=embed)

        # ---
        # global message_id   # pylint: disable=W0603
        # global channel_id   # pylint: disable=W0603

        # message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.DRIVERS_ROLE_ID),
        #                                                          constants.RIDES_MESSAGE1)
        # await interaction.response.send_message(message_to_send)

        # message_obj: discord.InteractionMessage = await interaction.original_response()

        # message_id = message_obj.id
        # channel_id = message_obj.channel.id

        # channel = bot.get_channel(channel_id)
        # target_message = await channel.fetch_message(message_id)

        # await target_message.add_reaction("👍")
        # await target_message.add_reaction("❌")

        # ---

        logger.info("Send command was executed")

        channel = bot.get_channel(916823070017204274)
        message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.DRIVERS_ROLE_ID),
                                                                 constants.RIDES_MESSAGE1)
        sent_message = await channel.send(message_to_send)
        await sent_message.add_reaction("👍")  
        await sent_message.add_reaction("❌")  
        await sent_message.add_reaction("➡️")  
        await sent_message.add_reaction("⬅️")  
        await sent_message.add_reaction("💩")  
        await interaction.response.send_message("Message sent!", delete_after=0)

    bot.run(TOKEN)



if __name__ == "__main__":
    run()
