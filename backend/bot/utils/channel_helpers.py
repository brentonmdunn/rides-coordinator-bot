"""Helpers for resolving Discord channel destinations."""

import os

from bot.core.enums import ChannelIds


def is_local() -> bool:
    """Return True when running in the local development environment."""
    return os.getenv("APP_ENV", "local") == "local"


def resolve_channel_id(channel_id: int) -> int:
    """
    Resolve the effective channel ID for an outbound notification.

    In production the channel is returned unchanged. In local development all
    notifications are redirected to the bots channel so real coordination
    channels are not spammed while developing.

    Args:
        channel_id: The intended destination channel ID.

    Returns:
        The channel ID to actually send to.
    """
    if is_local():
        return int(ChannelIds.BOT_STUFF__BOTS)
    return channel_id
