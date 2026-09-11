"""Service for route building and location matching."""

import logging
from datetime import datetime, timedelta

from bot.services.pickup_locations_service import RoutingContext
from bot.utils.parsing import parse_time

logger = logging.getLogger(__name__)


class RouteService:
    """Handles route building and fuzzy location matching."""

    @staticmethod
    def get_pickup_location_fuzzy(routing: RoutingContext, input_loc: str) -> str | None:
        """
        Get the fuzzy matched pickup location name from an input string.

        Args:
            routing (RoutingContext): Snapshot of the routing graph and settings.
            input_loc (str): The input location string.

        Returns:
            str | None: The matched pickup location name or None if no match.
        """
        return routing.fuzzy_match(input_loc)

    @staticmethod
    def resolve_location(routing: RoutingContext, token: str) -> str:
        """
        Resolve an input string to a pickup location name (exact, then fuzzy).

        Args:
            routing (RoutingContext): Snapshot of the routing graph and settings.
            token (str): The input location string.

        Returns:
            The matched pickup location name.

        Raises:
            ValueError: If no location matches.
        """
        lowered = token.strip().lower()
        for name in routing.active_names:
            if name.lower() == lowered:
                return name
        match = routing.fuzzy_match(token)
        if match is None:
            raise ValueError(f"Invalid location: {token}")
        return match

    @staticmethod
    def make_route_from_names(
        routing: RoutingContext, locations: list[str], leave_time: str
    ) -> str:
        """
        Makes a route from a list of location input strings.

        Args:
            routing (RoutingContext): Snapshot of the routing graph and settings.
            locations: Location input strings in pickup order.
            leave_time: The leave time for the route.

        Returns:
            The route as a string.

        Raises:
            ValueError: If a location cannot be resolved.
        """
        curr_leave_time = parse_time(leave_time)
        resolved = [RouteService.resolve_location(routing, token) for token in locations]

        drive_formatted: list[str] = []
        logger.debug(f"{resolved=}")

        reversed_locations = list(reversed(resolved))
        for idx, location in enumerate(reversed_locations):
            if idx != 0:
                time_between = routing.pickup_adjustment + routing.lookup_time(
                    location, reversed_locations[idx - 1]
                )
                logger.debug(f"{time_between=}")
                dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
                new_datetime = dummy_datetime - timedelta(minutes=time_between)
                curr_leave_time = new_datetime.time()

            logger.debug(f"{curr_leave_time=}")
            logger.debug(f"{location=}")
            base_string = f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} {location}"

            map_url = routing.map_url(location)
            if map_url:
                formatted_string = f"{base_string} ([Google Maps](<{map_url}>))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)

        logger.debug(f"{drive_formatted=}")

        return ", ".join(reversed(drive_formatted))

    @staticmethod
    def make_route(routing: RoutingContext, locations: str, leave_time: str) -> str:
        """
        Makes a route from a space-separated string of location tokens.

        Args:
            routing (RoutingContext): Snapshot of the routing graph and settings.
            locations: The locations to make a route for (space-separated tokens).
            leave_time: The leave time for the route.

        Returns:
            The route as a string.
        """
        return RouteService.make_route_from_names(routing, locations.split(), leave_time)
