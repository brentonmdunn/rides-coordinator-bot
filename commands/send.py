"""!send command"""

import random
from typing import List

import discord
import utils.ping as ping

async def execute(
        message: discord.message.Message,
        rides_message: str,
        reacts: List[str],
        role_id: int) -> int:
    """Sends message that users can react to."""

    to_send: str = ping.create_message(ping.get_role(message.guild, role_id), rides_message)
    sent_message: discord.message.Message = await message.channel.send(to_send)
    message_id = sent_message.id

    # Adds random reaction for ride
    current_reaction = random.randint(0, len(reacts) - 1)
    await sent_message.add_reaction(reacts[current_reaction])
    print(current_reaction)

    return message_id
