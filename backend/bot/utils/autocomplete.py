"""utils/autocomplete.py"""

from discord import app_commands

from bot.core.enums import CampusLivingLocations
from bot.utils.constants import LSCC_DAYS


async def lscc_day_autocomplete(
    _,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Command autocomplete for LSCC event days (currently Friday and Sunday).

    Args:
        _: The interaction object (unused).
        current (str): The current input string.

    Returns:
        list[app_commands.Choice[str]]: A list of matching choices.
    """
    return [
        app_commands.Choice(name=day, value=day)
        for day in LSCC_DAYS
        if current.lower() in day.lower()
    ]


async def location_autocomplete(
    _,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Command autocomplete for campus living locations.

    Args:
        _: The interaction object (unused).
        current (str): The current input string.

    Returns:
        list[app_commands.Choice[str]]: A list of matching choices.
    """
    locations = [location.value for location in CampusLivingLocations]
    return [
        app_commands.Choice(name=location, value=location)
        for location in locations
        if current.lower() in location.lower()
    ]
