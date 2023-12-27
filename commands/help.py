"""!help command"""

import discord

async def execute(message: discord.message.Message) -> None:
    """Instructions for !help command"""
    await message.channel.send("""```!send - sends ride message \n!get_reactions - lists users who have reacted \n!group - groups users by location```""")