"""Service for syncing location data from Google Sheets CSV."""

import csv
import io
import logging
import os
from collections.abc import Callable

import httpx
from dotenv import load_dotenv

from bot.core.database import AsyncSessionLocal
from bot.core.enums import CanBeDriver, ClassYear
from bot.core.models import Locations as LocationsModel
from bot.repositories.locations_repository import LocationsRepository

logger = logging.getLogger(__name__)

load_dotenv()

LSCC_PPL_CSV_URL = os.getenv("LSCC_PPL_CSV_URL")


class CsvSyncService:
    """Handles syncing location data from a Google Sheets CSV."""

    async def sync_locations(self):
        """
        Syncs the Google Sheet with database table ``locations``.

        Raises:
            Exception: If LSCC_PPL_CSV_URL is not set or data retrieval fails.
        """
        logger.info("Syncing locations...")
        if not LSCC_PPL_CSV_URL:
            raise Exception("LSCC_PPL_CSV_URL environment variable not set.")

        async with httpx.AsyncClient() as client:
            response = await client.get(LSCC_PPL_CSV_URL)

        if response.status_code != 200:
            raise Exception("Failed to retrieve data.")

        csv_data = response.content.decode("utf-8")
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)

        # Validate that all required columns exist
        required_columns = ["Name", "Discord Username", "Year", "Location", "Driver"]
        if reader.fieldnames is None:
            raise Exception("CSV file is empty or has no header row.")

        missing_columns = [col for col in required_columns if col not in reader.fieldnames]
        if missing_columns:
            raise Exception(
                f"CSV is missing required columns: {', '.join(missing_columns)}. "
                f"Found columns: {', '.join(reader.fieldnames)}"
            )

        locations_to_add = []
        for row in reader:
            name = self._get_info(row, "Name")
            if not name:
                continue

            locations_to_add.append(
                LocationsModel(
                    name=name.title(),
                    discord_username=self._get_info(row, "Discord Username"),
                    year=self._get_info(row, "Year", self._verify_year),
                    location=self._get_info(row, "Location"),
                    driver=self._get_info(row, "Driver", self._verify_driver),
                )
            )

        async with AsyncSessionLocal() as session:
            await LocationsRepository.sync_locations(session, locations_to_add)

        logger.info("Finished syncing locations csv with table.")

    def _verify_year(self, year: str) -> bool:
        """Verifies if the year is valid."""
        return year in [y.value for y in ClassYear]

    def _verify_driver(self, driver: str) -> bool:
        """Verifies if the driver status is valid."""
        return driver in [d.value for d in CanBeDriver]

    def _get_info(self, data: dict, key: str, verify_schema: Callable | None = None) -> str | None:
        """Extracts and verifies information from a dictionary."""
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            return None

        info = value.strip().lower()
        if verify_schema is not None and not verify_schema(info):
            return None
        return info
