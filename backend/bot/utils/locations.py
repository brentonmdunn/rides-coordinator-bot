"""utils/locations.py"""

import heapq

from bot.core.enums import PickupLocations
from bot.core.logger import logger
from bot.core.schemas import LocationQuery

LOCATIONS_MATRIX = {
    PickupLocations.MUIR: [(PickupLocations.SIXTH, 1), (PickupLocations.EIGHTH, 2)],
    PickupLocations.SIXTH: [(PickupLocations.MUIR, 1), (PickupLocations.MARSHALL, 1)],
    PickupLocations.MARSHALL: [(PickupLocations.SIXTH, 1), (PickupLocations.ERC, 1)],
    PickupLocations.ERC: [(PickupLocations.MARSHALL, 1), (PickupLocations.SEVENTH, 1)],
    PickupLocations.SEVENTH: [
        (PickupLocations.ERC, 1),
        (PickupLocations.WARREN_EQL, 4),
        (PickupLocations.GEISEL_LOOP, 5),
        ("END", 20),
    ],
    PickupLocations.WARREN_EQL: [
        (PickupLocations.SEVENTH, 4),
        (PickupLocations.RITA, 8),
        (PickupLocations.INNOVATION, 1),
        (PickupLocations.GEISEL_LOOP, 3),
        (PickupLocations.PCYN_LOOP, 6),
    ],
    PickupLocations.GEISEL_LOOP: [(PickupLocations.WARREN_EQL, 3), (PickupLocations.SEVENTH, 5)],
    PickupLocations.RITA: [
        (PickupLocations.WARREN_EQL, 8),
        (PickupLocations.INNOVATION, 7),
        (PickupLocations.EIGHTH, 4),
        ("START", 10),
    ],
    PickupLocations.INNOVATION: [
        (PickupLocations.WARREN_EQL, 1),
        (PickupLocations.RITA, 7),
        ("START", 10),
        ("END", 20),
    ],
    PickupLocations.EIGHTH: [
        (PickupLocations.RITA, 4),
        (PickupLocations.MUIR, 2),
        ("START", 10),
        (PickupLocations.PCYN_LOOP, 5),
    ],
    PickupLocations.PCYN_LOOP: [
        (PickupLocations.EIGHTH, 5),
        (PickupLocations.WARREN_EQL, 6),
        ("START", 10),
        ("END", 20),
    ],
    "START": [
        (PickupLocations.INNOVATION, 10),
        (PickupLocations.EIGHTH, 10),
        (PickupLocations.RITA, 10),
    ],
    "END": [(PickupLocations.INNOVATION, 20), (PickupLocations.SEVENTH, 20)],
}


def lookup_time(query: LocationQuery) -> int:
    """
    Looks up the travel time between two locations using a Pydantic model for input.

    Args:
        query: A LocationQuery model containing the start and end locations.

    Returns:
        The travel time as an integer, or raises an exception if the path is not found.
    """
    logger.debug(f"{query=}")
    distances = {location: float("inf") for location in LOCATIONS_MATRIX}
    distances[query.start_location] = 0
    priority_queue = [(0, query.start_location)]

    while priority_queue:
        current_distance, current_location = heapq.heappop(priority_queue)

        if current_distance > distances[current_location]:
            continue

        if current_location == query.end_location:
            return distances[query.end_location]

        for neighbor, time in LOCATIONS_MATRIX.get(current_location, []):
            distance = current_distance + time
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                heapq.heappush(priority_queue, (distance, neighbor))

    return None
