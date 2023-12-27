from typing import Set
import discord

async def get_users(message, message_id, bot_name) -> Set[discord.member.Member]:
    """Returns set of member objects of users who reacted."""
    target_message = await message.channel.fetch_message(message_id)

    # Iterate through reactions and collect users who reacted
    reaction_users: Set[discord.member.Member] = set()
    for reaction in target_message.reactions:
        async for user in reaction.users():
            if str(user) == bot_name:
                continue
            reaction_users.add(user)
    
    return reaction_users