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
    """Generate a Google Maps URL for a pickup location.

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


def get_map_links() -> dict[PickupLocations, str]:
    """Generate a dict of all pickup locations to their Google Maps URLs.

    Returns:
        Dictionary mapping PickupLocations to Google Maps URL strings.
    """
    return {loc: get_map_url(loc) for loc in MAP_LOCATIONS}
