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


async def cmd_is_allowed(
    interaction: discord.Interaction,
    channel_id: int,
    whitelisted_channels: set[int] = BOT_TESTING_CHANNELS,
) -> bool:
    """Checks if a command is allowed in the current channel.

    Args:
        interaction (discord.Interaction): The interaction object.
        channel_id (int): The ID of the channel where the command was invoked.
        whitelisted_channels (set[int], optional): A set of allowed channel IDs.
            Defaults to BOT_TESTING_CHANNELS.

    Returns:
        bool: True if the command is allowed, False otherwise.
    """
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
