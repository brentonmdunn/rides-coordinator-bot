"""!help command"""

import discord


async def execute(message: discord.message.Message) -> None:
    """Lists commands that user can run."""
    await message.channel.send("""```!send - sends ride message \n!get_reactions - lists users who have reacted \n!group - groups users by location```""")
