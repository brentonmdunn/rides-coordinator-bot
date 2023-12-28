"""!help command"""

import discord


async def execute(message: discord.message.Message) -> None:
    """Lists commands that the user can run."""
    command_list = (
        "!send - sends ride message"
        "\n!get_reactions - lists users who have reacted"
        "\n!group - groups users by location"
    )
    await message.channel.send(f"```{command_list}```")
