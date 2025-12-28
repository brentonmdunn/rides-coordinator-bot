"""utils/format_message.py

Helper functions to format messages.
"""

from bot.core.enums import ChannelIds, RoleIds


def ping_role(role_id: RoleIds) -> str:
    """Returns formatted message that pings a role.

    Args:
        role_id (RoleIds): The ID of the role to ping.

    Returns:
        str: The formatted string to ping the role.
    """
    return f"<@&{role_id}> "


def ping_role_with_message(role_id: RoleIds, message: str) -> str:
    """Adds @role to message.

    Args:
        role_id (RoleIds): The ID of the role to ping.
        message (str): The message to append.

    Returns:
        str: The formatted string with the role ping and message.
    """
    return f"<@&{role_id}> {message}"


def ping_channel(channel_id: ChannelIds) -> str:
    """Returns formatted message that pings a channel.

    Args:
        channel_id (ChannelIds): The ID of the channel to ping.

    Returns:
        str: The formatted string to ping the channel.
    """
    return f"<#{channel_id}> "


def ping_user(user_id: int) -> str:
    """Returns formatted message that pings a user.

    Args:
        user_id (int): The ID of the user to ping.

    Returns:
        str: The formatted string to ping the user.
    """
    return f"<@{user_id}> "


def message_link(guild_id: int, channel_id: int, message_id: int) -> str:
    """Generates a link to a specific Discord message.

    Args:
        guild_id (int): The ID of the guild.
        channel_id (int): The ID of the channel.
        message_id (int): The ID of the message.

    Returns:
        str: The URL to the message.
    """
    return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
