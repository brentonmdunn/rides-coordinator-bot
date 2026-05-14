"""Contains constants"""

from bot.core.enums import DaysOfWeek, PickupLocations

GUILD_ID = 916817752918982716

LSCC_DAYS = [DaysOfWeek.FRIDAY, DaysOfWeek.SUNDAY]

# Coordinates (lat, lng) for each pickup location.
# Source of truth — Google Maps links are generated from these.
MAP_LOCATIONS: dict[PickupLocations, tuple[float, float]] = {
    PickupLocations.SIXTH: (32.881096, -117.242020),
    PickupLocations.SEVENTH: (32.888203, -117.242347),
    PickupLocations.MARSHALL: (32.883187, -117.241281),
    PickupLocations.ERC: (32.885294, -117.242357),
    PickupLocations.MUIR: (32.878133, -117.243361),
    PickupLocations.EIGHTH: (32.873411, -117.242997),
    PickupLocations.INNOVATION: (32.879118, -117.231663),
    PickupLocations.RITA: (32.873065, -117.235532),
    PickupLocations.WARREN_EQL: (32.883587, -117.233687),
    PickupLocations.WARREN_JST: (32.883156, -117.232222),
    PickupLocations.GEISEL_LOOP: (32.881598, -117.238614),
    PickupLocations.PCYN_LOOP: (32.878366, -117.234230),
}


def get_map_url(location: PickupLocations) -> str | None:
    """
    Generate a Google Maps URL for a pickup location.

    Args:
        location: The pickup location enum member.

    Returns:
        Google Maps URL string, or None if coordinates are not defined.
    """
    coords = MAP_LOCATIONS.get(location)
    if coords is None:
        return None
    lat, lng = coords
    return f"https://www.google.com/maps?q={lat},{lng}"


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


def get_map_links() -> dict[PickupLocations, str]:
    """
    Generate a dict of all pickup locations to their Google Maps URLs.

    Returns:
        Dictionary mapping PickupLocations to Google Maps URL strings.
    """
    return {loc: get_map_url(loc) for loc in MAP_LOCATIONS}


# Session / auth (bot side)
SESSION_TTL_DAYS = 30
SESSION_TOUCH_THROTTLE_MINUTES = 5

# LLM
GEMINI_MODEL = "gemini-2.5-flash"
LLM_RETRY_ATTEMPTS = 4
LLM_RETRY_WAIT_SECONDS = 5
LLM_JSON_CODEBOX_START_OFFSET = 8
LLM_JSON_CODEBOX_END_OFFSET = -3

# Ride grouping
RIDE_GROUPING_PICKUP_ADJUSTMENT = 1

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
RIDE_CYCLE_START_HOUR = 12  # noon

# Lifecycle
REDIS_CONNECTION_TIMEOUT = 5.0

# Default group rides capacity
GROUP_RIDES_DEFAULT_CAPACITY = "44444"
