"""!send command"""

import random
import discord
import utils.ping as ping

async def execute(message: discord.message.Message, needs_ride, RIDES_MESSAGE, REACTS, ROLE_ID) -> int:
    """Instructions for !send command"""
    # Clears list before each reaction
    needs_ride = []

    to_send: str = ping.create_message(ping.get_role(message.guild, ROLE_ID), RIDES_MESSAGE)
    sent_message: discord.message.Message = await message.channel.send(to_send)
    message_id = sent_message.id

    # Adds random reaction for ride
    current_reaction = random.randint(0, len(REACTS) - 1)
    await sent_message.add_reaction(REACTS[current_reaction])
    print(current_reaction)

    return message_id