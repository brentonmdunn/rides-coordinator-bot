"""utils/channel_whitelist.py"""

import discord

from app.core.enums import ChannelIds
from app.core.logger import logger

BOT_TESTING_CHANNELS = {
    ChannelIds.BOT_STUFF__BOTS,
    ChannelIds.BOT_STUFF__BOT_SPAM_2,
    ChannelIds.BOT_STUFF__BOT_LOGS,
}
LOCATIONS_CHANNELS_WHITELIST = BOT_TESTING_CHANNELS | {
    ChannelIds.SERVING__DRIVER_BOT_SPAM,
    ChannelIds.SERVING__LEADERSHIP,
    ChannelIds.SERVING__DRIVER_CHAT_WOOOOO,
}


async def is_allowed_locations(
    interaction: discord.Interaction,
    channel_id: int,
    whitelisted_channels: set[int] = BOT_TESTING_CHANNELS,
) -> bool:
    if channel_id in whitelisted_channels:
        return True

    await interaction.response.send_message(
        f"`/{interaction.data['name']}` cannot be used in #{interaction.channel}.",
        ephemeral=True,
    )
    logger.info(
        "/%s not allowed in #%s by %s",
        interaction.data["name"],
        interaction.channel,
        interaction.user,
    )
    return False
