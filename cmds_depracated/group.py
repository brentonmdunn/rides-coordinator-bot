# """!group command"""

# from typing import Dict, Set
# import discord
# import utils.reactions as reactions

# async def execute(message: discord.message.Message,
#                   message_id: int,
#                   bot_name: str,
#                   user_info: Dict[str, Dict[str, str]]) -> None:
#     """Groups users by location."""

#     # Fetch the message for which you want to get reactions
#     if message_id is None:
#         await message.channel.send("Message has not sent yet.")
#         return

#     location_groups: Dict[str, Set[discord.member.Member]] = dict()

#     reaction_users: Set[discord.member.Member] = await reactions.get_users(message, message_id, bot_name)

#     for user in reaction_users:
#         if str(user) == bot_name:
#             continue
#         user_identifier: str = str(user)
#         user_location: str = user_info[user_identifier]["location"]
#         if user_location in location_groups:
#             location_groups[user_location].add(user_identifier)
#         else:
#             location_groups[user_location] = {user_identifier}

#     for location, users in location_groups.items():
#         users_at_location = ", ".join(user_info[user]['fname'] for user in users)
#         await message.channel.send(f"{location}: {users_at_location}")


"""!group command"""

from typing import Dict, Set
import discord
import utils.reactions as reactions

async def execute(interaction: discord.Interaction,
                  message_id: int,
                  bot_name: str,
                  user_info: Dict[str, Dict[str, str]]) -> None:
    """Groups users by location."""

    # Fetch the message for which you want to get reactions
    if message_id is None:
        await interaction.response.send_message("Message has not sent yet.")
        return

    location_groups: Dict[str, Set[discord.member.Member]] = dict()

    reaction_users: Set[discord.member.Member] = await reactions.get_users(message, message_id, bot_name)

    for user in reaction_users:
        if str(user) == bot_name:
            continue
        user_identifier: str = str(user)
        user_location: str = user_info[user_identifier]["location"]
        if user_location in location_groups:
            location_groups[user_location].add(user_identifier)
        else:
            location_groups[user_location] = {user_identifier}

    for location, users in location_groups.items():
        users_at_location = ", ".join(user_info[user]['fname'] for user in users)
        await interaction.response.send_message(f"{location}: {users_at_location}")
