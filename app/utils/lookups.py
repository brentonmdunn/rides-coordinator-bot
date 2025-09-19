import csv
import functools
import gc
import io
import os
from collections.abc import Callable

import requests
from dotenv import load_dotenv
from sqlalchemy import delete, func, or_, select

from app.core.database import AsyncSessionLocal
from app.core.enums import CanBeDriver, ClassYear
from app.core.logger import logger
from app.core.models import Locations

load_dotenv()

RIDES_LOCATIONS_CSV_URL = os.getenv("RIDES_LOCATIONS_CSV_URL")


def sync_on_cache_miss(func):
    """
    A decorator for lookup functions. If the decorated function returns None
    (a cache miss), it triggers a database sync and retries the function once.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # First attempt to get data from the database (cache)
        result = await func(*args, **kwargs)
        if result is not None:
            return result

        # Cache miss: log, sync from the source of truth, and retry
        logger.info(f"Cache miss in {func.__name__}. Triggering sync and retrying.")
        await sync()

        # Second attempt
        return await func(*args, **kwargs)

    return wrapper


@sync_on_cache_miss
async def get_location(name: str, discord_only: bool = False) -> list[tuple[str, str]] | None:
    """
    Searches up locations based on a name (searches both name and username). Uses contains.

    Args:
        name (str): Name to search for.

    Returns:
        List of (name, location) tuples or None if not found.
    """
    if discord_only:
        async with AsyncSessionLocal() as session:
            from app.core.models import Locations as LocationsModel

            stmt = select(LocationsModel.name, LocationsModel.location).where(
                or_(
                    func.lower(LocationsModel.discord_username).contains(name.lower()),
                )
            )
            result = await session.execute(stmt)
            possible_people = result.all()
    else:
        async with AsyncSessionLocal() as session:
            from app.core.models import Locations as LocationsModel

            stmt = select(LocationsModel.name, LocationsModel.location).where(
                or_(
                    func.lower(LocationsModel.name).contains(name.lower()),
                    func.lower(LocationsModel.discord_username).contains(name.lower()),
                )
            )
            result = await session.execute(stmt)
            possible_people = result.all()

    if not possible_people:
        return None
    return possible_people


@sync_on_cache_miss
async def get_discord_username(name: str) -> str | None:
    """
    Gets Discord username of person. The database is treated as a cache.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Locations.discord_username).where(func.lower(Locations.name) == name.lower())
        result = await session.execute(stmt)
        discord_username = result.scalars().first()
        return discord_username


@sync_on_cache_miss
async def get_name(discord_username: str) -> str | None:
    """
    Gets name of person. The database is treated as a cache.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Locations.name).where(
            func.lower(Locations.discord_username) == discord_username.lower()
        )
        result = await session.execute(stmt)
        name = result.scalars().first()
        return name


async def get_name_location_no_sync(discord_username: str) -> tuple[str, str] | None:
    """
    Gets name and location of person. This method does not automatically sync
    on cache miss.

    Args:
        discord_username: Discord username to search for.

    Returns:
        Tuple of (name, location) or None if not found.
    """

    async with AsyncSessionLocal() as session:
        stmt = select(Locations.name, Locations.location).where(
            func.lower(Locations.discord_username) == str(discord_username).lower()
        )
        result = await session.execute(stmt)
        person = result.first()
        return person


def _verify_year(year: str) -> bool:
    return year in [year.value for year in ClassYear]


def _verify_driver(driver: str) -> bool:
    return driver in [driver.value for driver in CanBeDriver]


def _get_info(data: dict, key: str, verify_schema: Callable | None = None) -> str | None:
    value = data.get(key)
    # Ensure value is a string and not just whitespace
    if not isinstance(value, str) or not value.strip():
        return None

    info = value.strip().lower()
    if verify_schema is not None and not verify_schema(info):
        return None
    return info


async def sync():
    """
    Syncs the Google Sheet with databas table `locations`.
    """
    logger.info("Syncing locations...")
    if not RIDES_LOCATIONS_CSV_URL:
        raise Exception("RIDES_LOCATIONS_CSV_URL environment variable not set.")

    response = requests.get(RIDES_LOCATIONS_CSV_URL)

    if response.status_code != 200:
        raise Exception("Failed to retrieve data.")

    csv_data = response.content.decode("utf-8")
    csv_file = io.StringIO(csv_data)
    reader = csv.DictReader(csv_file)

    locations_to_add = []
    for row in reader:
        name = _get_info(row, "Name")
        if not name:
            # The 'name' column is not nullable, so we skip rows without a valid name.
            continue

        locations_to_add.append(
            Locations(
                name=name.title(),
                discord_username=_get_info(row, "Discord Username"),
                year=_get_info(row, "Year", _verify_year),
                location=_get_info(row, "Location"),
                driver=_get_info(row, "Driver", _verify_driver),
            )
        )

    async with AsyncSessionLocal() as session:
        await session.execute(delete(Locations))
        if locations_to_add:
            session.add_all(locations_to_add)
        await session.commit()

    reader = None
    locations_to_add = None
    gc.collect()
    logger.info("Finished syncing locations csv with table.")
