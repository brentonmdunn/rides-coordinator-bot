from discord import app_commands

from app.core.enums import CampusLivingLocations
from app.utils.constants import LSCC_DAYS


async def lscc_day_autocomplete(
    _,
    current: str,
) -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=day, value=day)
        for day in LSCC_DAYS
        if current.lower() in day.lower()
    ]


async def location_autocomplete(
    _,
    current: str,
) -> list[app_commands.Choice[str]]:
    locations = [location.value for location in CampusLivingLocations]
    return [
        app_commands.Choice(name=location, value=location)
        for location in locations
        if current.lower() in location.lower()
    ]
