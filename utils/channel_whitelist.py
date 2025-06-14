"""
utils/channel_whitelist.py
"""

import discord

from enums import ChannelIds
from logger import logger

LOCATIONS_CHANNELS_WHITELIST = [
    ChannelIds.SERVING__DRIVER_BOT_SPAM,
    ChannelIds.SERVING__LEADERSHIP,
    ChannelIds.SERVING__DRIVER_CHAT_WOOOOO,
]

BOT_TESTING_CHANNELS = [
    ChannelIds.BOT_STUFF__BOTS,
    ChannelIds.BOT_STUFF__BOT_SPAM_2,
    ChannelIds.BOT_STUFF__BOT_LOGS,
]


async def is_allowed_locations(
    interaction: discord.Interaction, channel_id: int
) -> bool:
    if channel_id in BOT_TESTING_CHANNELS:
        return True
    if channel_id not in LOCATIONS_CHANNELS_WHITELIST:
        await interaction.response.send_message(
            "Command cannot be used in this channel.", ephemeral=True
        )
        logger.info(
            "Command not allowed in #%s by %s", interaction.channel, interaction.user
        )
        return False
    return True
