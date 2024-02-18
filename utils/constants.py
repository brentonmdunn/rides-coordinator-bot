"""Contains constants"""

from typing import List

SEND_DESCRIPTION: str = "Sends the message for people to react to for rides."
GROUP_DESCRIPTION: str = "Groups people by pickup location."
HELP_DESCRIPTION: str = "List of slash commands available."

ADMIN_LIST_USER_INFO_DESCRIPTION: str = "Gets all user info or a named user (optional param)."
ADMIN_GET_REACTION_USERS_DESCRIPTION: str = "Gets list of users who reacted to message."
ADMIN_HELP_DESCRIPTION: str = "Slash commands available for admins."

RIDES_MESSAGE1: str = "React if you want a ride to class this Sunday (leave around 8:40)"
RIDES_MESSAGE2: str = "React if you want a ride to Sunday Service (leave around 10:10)"

REACTS: List[str] = ['🥐', '🧁', '🍩', '🌋', '🦕', '🐸', '🐟', '🐻', '🦔']
# ROLE_ID: int = 1188019586470256713
ROLE_ID = 940467850261450752 

RIDES_CHANNEL_ID = 939950319721406464
BOT_SPAM_2_CHANNEL_ID = 1208264072638898217
BOTS_CHANNEL_ID = 916823070017204274
BOTS_SETTINGS_BACKUP_CHANNEL_ID = 1208472182548725841
BOT_LOGS_CHANNEL_ID = 1208482668820570162

AUTHORIZED_ADMIN: List[str] = ['brentond', 'kendruh.']

CAMPUS: List[str] = ['Eighth', 'Revelle', 'Muir', 'Sixth', 'Marshall', 'ERC', 'Seventh', 'Warren']