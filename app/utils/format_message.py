"""utils/format_message.py

Helper functions to format messages.
"""

from app.core.enums import ChannelIds, RoleIds


def ping_role(role_id: RoleIds) -> str:
    """Returns formatted message that pings a role."""
    return f"<@&{role_id}> "


def ping_role_with_message(role_id: RoleIds, message: str) -> str:
    """Adds @role to message."""
    return f"<@&{role_id}> {message}"


def ping_channel(channel_id: ChannelIds) -> str:
    """Returns formatted message that pings a channel."""
    return f"<#{channel_id}> "


def ping_user(user_id):
    return f"<@{user_id}> "
