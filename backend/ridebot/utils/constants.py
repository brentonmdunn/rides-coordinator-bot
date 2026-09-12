"""Contains constants"""

import discord

from shared.core.enums import CampusLivingLocations, DaysOfWeek, EmbedColorChoice, Emoji

GUILD_ID = 916817752918982716

# Preset embed color palette for ask-rides message templates.
EMBED_COLOR_MAP: dict[EmbedColorChoice, discord.Color] = {
    EmbedColorChoice.TEAL: discord.Color.from_rgb(100, 200, 150),
    EmbedColorChoice.GREEN: discord.Color.green(),
    EmbedColorChoice.BLUE: discord.Color.blue(),
    EmbedColorChoice.BLURPLE: discord.Color.blurple(),
    EmbedColorChoice.PINK: discord.Color.from_rgb(227, 132, 212),
    EmbedColorChoice.MAGENTA: discord.Color.magenta(),
    EmbedColorChoice.ORANGE: discord.Color.orange(),
    EmbedColorChoice.YELLOW: discord.Color.gold(),
    EmbedColorChoice.RED: discord.Color.red(),
    EmbedColorChoice.PURPLE: discord.Color.purple(),
}

LSCC_DAYS = [DaysOfWeek.FRIDAY, DaysOfWeek.SUNDAY]

# Ride-reaction emojis that can be tagged on a non-Discord pickup, mapped to a
# human-readable label. Keys double as the allowlist of valid emoji tags.
RIDE_REACTION_LABELS: dict[str, str] = {
    Emoji.LUNCH: "Lunch",
    Emoji.NO_LUNCH: "No lunch",
    Emoji.SOMETHING_ELSE: "Something else",
    Emoji.FRIDAY_FELLOWSHIP: "Friday Fellowship",
    Emoji.SUNDAY_CLASS: "Sunday class",
}

SCHOLARS_LOCATIONS = [
    "revelle",
    "muir",
    "sixth",
    "marshall",
    "erc",
    "seventh",
    "new marshall",
    "eighth",
]

WARREN_PEPPER_CANYON_LOCATIONS = [
    "warren",
    "pcyn",
    "pce",
    "pcw",
    "pepper canyon east",
    "pepper canyon west",
]

RITA_LOCATIONS = ["rita"]


# LLM
GEMINI_MODEL = "gemini-2.5-flash"
LLM_RETRY_ATTEMPTS = 4
LLM_RETRY_WAIT_SECONDS = 5

# Ride coverage
COVERAGE_STATUS_DEFAULT_HOURS = 24

# Ask rides job
ASK_RIDES_ACTIVE_CACHE_TTL = 60  # seconds (during Wednesday active period)
ASK_RIDES_HOURLY_CACHE_TTL = 60 * 60  # seconds (during active hours)
ASK_RIDES_OFF_HOURS_CACHE_TTL = 7 * 60 * 60  # seconds (off-hours)
ASK_RIDES_MESSAGE_HISTORY_LIMIT = 20

# Cache
CACHE_DEFAULT_MAX_SIZE = 128
REACTION_CACHE_ACTIVE_TTL = 65 * 60  # 65 minutes
REACTION_CACHE_OFF_HOURS_TTL = 7 * 60 * 60  # 7 hours

# Time helpers
DAYS_IN_WEEK = 7
ACTIVE_HOURS_START = 7  # 7 AM
ACTIVE_HOURS_END = 1  # 1 AM next day

# Default group rides capacity
GROUP_RIDES_DEFAULT_CAPACITY = "44444"

# Admin UI
PICKUP_INFO_PAGE_URL = "https://ridebot.springroll.app/pickup-info"

# Pickup spots a living area is sometimes collected at besides its mapped one, shown
# to riders after the usual spot. Names must match a pickup location on the
# Locations page; an unknown or inactive name is skipped rather than linked.
ALTERNATE_PICKUP_SPOTS: dict[str, tuple[str, ...]] = {
    CampusLivingLocations.MARSHALL.value: ("Geisel Loop",),
}

# Pickup-info buttons. These ids are stored inside every posted message, so
# changing a value orphans buttons already in Discord.
PICKUP_INFO_ON_CAMPUS_CUSTOM_ID = "ridebot:pickup-info:on-campus"
PICKUP_INFO_OFF_CAMPUS_CUSTOM_ID = "ridebot:pickup-info:off-campus"
PICKUP_INFO_SDSU_CUSTOM_ID = "ridebot:pickup-info:sdsu"

# Used to recognize one of our own prompts when deciding whether to re-post.
PICKUP_INFO_BUTTON_CUSTOM_IDS = frozenset(
    {
        PICKUP_INFO_ON_CAMPUS_CUSTOM_ID,
        PICKUP_INFO_OFF_CAMPUS_CUSTOM_ID,
        PICKUP_INFO_SDSU_CUSTOM_ID,
    }
)
