"""Service for route building and location matching."""

import logging
from datetime import datetime, timedelta

from rapidfuzz import fuzz, process

from bot.core.enums import PickupLocations
from bot.core.schemas import LocationQuery
from bot.services.ride_grouping import PICKUP_ADJUSTMENT
from bot.utils.constants import get_map_url
from bot.utils.locations import lookup_time
from bot.utils.parsing import parse_time

logger = logging.getLogger(__name__)


class RouteService:
    """Handles route building and fuzzy location matching."""

    @staticmethod
    def get_pickup_location_fuzzy(input_loc: str) -> PickupLocations | None:
        """
        Get the fuzzy matched pickup location from an input string.

        Args:
            input_loc (str): The input location string.

        Returns:
            PickupLocations | None: The matched pickup location or None if no match.
        """
        choices = {e.value: e for e in PickupLocations}

        result = process.extractOne(
            input_loc,
            choices.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=65,
        )

        if result:
            return choices[result[0]]

        result = process.extractOne(
            input_loc,
            choices.keys(),
            scorer=fuzz.partial_ratio,
            score_cutoff=60,
        )

        if result:
            logger.debug(f"{result=}")
            logger.debug(f"Fallback match: '{input_loc}' -> '{result[0]}' (Score: {result[1]})")
            return choices[result[0]]

        return None

    @staticmethod
    def make_route(locations: str, leave_time: str) -> str:
        """
        Makes route based on specified locations.

        Args:
            locations: The locations to make a route for.
            leave_time: The leave time for the route.

        Returns:
            The route as a string.
        """
        curr_leave_time = parse_time(leave_time)
        locations_list = locations.split()
        locations_list_actual = []
        for location in locations_list:
            try:
                actual_location = PickupLocations[location.upper()]
                locations_list_actual.append(actual_location)
            except KeyError:
                if (
                    actual_location := RouteService.get_pickup_location_fuzzy(location)
                ) is not None:
                    locations_list_actual.append(actual_location)
                else:
                    raise ValueError(f"Invalid location: {location}") from None

        drive_formatted: list[str] = []
        logger.debug(f"{locations_list_actual=}")

        reversed_locations = list(reversed(locations_list_actual))
        for idx, location in enumerate(reversed_locations):
            if idx != 0:
                time_between = PICKUP_ADJUSTMENT + lookup_time(
                    LocationQuery(start_location=location, end_location=reversed_locations[idx - 1])
                )
                logger.debug(f"{time_between=}")
                dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
                new_datetime = dummy_datetime - timedelta(minutes=time_between)
                curr_leave_time = new_datetime.time()

            logger.debug(f"{curr_leave_time=}")
            logger.debug(f"{location=}")
            base_string = (
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} {location.value}"
            )

            map_url = get_map_url(location)
            if map_url:
                formatted_string = f"{base_string} ([Google Maps](<{map_url}>))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)

        logger.debug(f"{drive_formatted=}")

        return ", ".join(reversed(drive_formatted))
