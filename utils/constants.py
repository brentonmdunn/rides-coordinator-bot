"""Contains constants"""

from typing import List

SEND_DESCRIPTION: str = "Sends the message for people to react to for rides."
GROUP_DESCRIPTION: str = "Groups people by pickup location."
HELP_DESCRIPTION: str = "List of slash commands available."

ADMIN_LIST_USER_INFO_DESCRIPTION: str = "Gets all user info or a named user (optional param)."
ADMIN_GET_REACTION_USERS_DESCRIPTION: str = "Gets list of users who reacted to message."
ADMIN_HELP_DESCRIPTION: str = "Slash commands available for admins."

RIDES_MESSAGE: str = "React for rides."
REACTS: List[str] = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']
ROLE_ID: int = 1188019586470256713

AUTHORIZED_ADMIN: List[str] = ['brentond', 'kendruh.']
