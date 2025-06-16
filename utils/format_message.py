"""utils/format_message.py

Helper functions to format messages.
"""

from enums import RoleIds


def ping_role(role_id: RoleIds) -> str:
    """Returns formatted message that pings a role."""
    return f"<@&{role_id}> "


def ping_role_with_message(role_id: RoleIds, message: str) -> str:
    """Adds @role to message."""
    return f"<@&{role_id}> {message}"
