from typing import Set
import discord
import utils.reactions as reactions
async def execute(message, message_id, bot_name):
    # Fetch the message for which you want to get reactions
    if message_id is None:
        await message.channel.send("Message has not sent yet.")
        return

    reaction_users: Set[discord.member.Member] = await reactions.get_users(message, message_id, bot_name)

    users_list = ", ".join(str(user) for user in reaction_users)
    await message.channel.send(f"Users who reacted: {users_list}")