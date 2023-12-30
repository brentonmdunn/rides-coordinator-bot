"""!get_reactions command"""

from typing import List, Set
import discord
import utils.reactions_depracated as reactions_depracated

async def execute(message: discord.message.Message, message_id: int, bot_name: str) -> None:
    """Sends list of users who reacted to message."""

    # Fetch the message for which you want to get reactions
    if message_id is None:
        await message.channel.send("Message has not sent yet.")
        return

    reaction_users: Set[discord.member.Member] = await reactions_depracated.get_users(message, message_id, bot_name)

    users_list: List[str] = ", ".join(str(user) for user in reaction_users)
    await message.channel.send(f"Users who reacted: {users_list}")
