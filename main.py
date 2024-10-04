"""Main functionality of bot"""


from discord.ext import commands, tasks

# Built in modules
import copy
import json
import os
from typing import Dict, List, Set, Union

# External modules
import discord
# from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import yaml

# Local modules
from logger import logger
import utils.ping as ping
import utils.constants as constants

# # Environment variables from .env file
# load_dotenv()
# TOKEN: str = os.getenv('TOKEN')
# BOT_NAME: str = os.getenv('BOT_NAME')
# # LOCATIONS_PATH: str = os.getenv('LOCATIONS_PATH')
# # EMERGENCY_CONTACT: int = int(os.getenv('EMERGENCY_CONTACT'))
# GUILD_ID: int = int(os.getenv('GUILD_ID'))

TOKEN: str = os.environ['TOKEN']
BOT_NAME: str = os.environ['BOT_NAME']
GUILD_ID: int = int(os.environ['GUILD_ID'])
DRIVERS_CHANNEL: int = int(os.environ['DRIVERS_CHANNEL'])


# Global variables
message_id: int = 0
channel_id: int = 0
new_message = ""


def run() -> None:
    """Main method for bot."""

    intents = discord.Intents.all()
    intents.messages = True
    intents.guilds = True
    bot = commands.Bot(command_prefix='!', intents=intents)


    @bot.event
    async def on_ready():
        """Runs when bot first starts up. Syncs slash commands with server."""
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s).")
        except Exception as e:      # pylint: disable=W0718
            print(e)


    @bot.tree.command(name="ask-drivers", description="Pings drivers to see who is available")
    async def ask_drivers(interaction: discord.Interaction, message: str) -> None:
        
  
        logger.info("ask-drivers command was executed")

        channel = bot.get_channel(DRIVERS_CHANNEL) # Currently on dev channel
        message_to_send: str = ping.create_message(ping.get_role(interaction.guild, constants.DRIVERS_ROLE_ID),
                                                                 message)
        sent_message = await channel.send(message_to_send)
        await sent_message.add_reaction("👍")  
        await sent_message.add_reaction("❌")  
        await sent_message.add_reaction("➡️")  
        await sent_message.add_reaction("⬅️")  
        await sent_message.add_reaction("💩")  

        # There needs to be something sent 
        await interaction.response.send_message("Message sent!", delete_after=0)

    bot.run(TOKEN)



if __name__ == "__main__":
    run()
