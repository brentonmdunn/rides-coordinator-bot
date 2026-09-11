"""utils/channels.py — environment-aware routing for outbound Discord messages."""

import os

from bot.core.enums import ChannelIds


def resolve_channel_id(channel_id: int) -> int:
    """
    Resolve the channel an outbound message should actually be sent to.

    When ``APP_ENV=local``, every outbound message is routed to
    ``ChannelIds.BOT_STUFF__BOTS`` so local development never posts in real
    channels. In any other environment, the intended channel is returned
    unchanged.

    Only use this for *sending* messages. Do not use it for incoming-event
    comparisons (reaction listeners, whitelists) or message scanning — those
    must keep referencing the real channel IDs.
    """
    if os.getenv("APP_ENV", "local") == "local":
        return int(ChannelIds.BOT_STUFF__BOTS)
    return int(channel_id)
