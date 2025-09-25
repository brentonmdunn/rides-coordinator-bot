import heapq

from app.core.enums import PickupLocations
from app.core.logger import logger
from app.core.schemas import LocationQuery

LOCATIONS_MATRIX = {
    PickupLocations.MUIR: [(PickupLocations.SIXTH, 1), (PickupLocations.EIGHTH, 2)],
    PickupLocations.SIXTH: [(PickupLocations.MUIR, 1), (PickupLocations.MARSHALL, 1)],
    PickupLocations.MARSHALL: [(PickupLocations.SIXTH, 1), (PickupLocations.ERC, 1)],
    PickupLocations.ERC: [(PickupLocations.MARSHALL, 1), (PickupLocations.SEVENTH, 1)],
    PickupLocations.SEVENTH: [(PickupLocations.ERC, 1), (PickupLocations.WARREN_EQL, 4)],
    PickupLocations.WARREN_EQL: [
        (PickupLocations.SEVENTH, 4),
        (PickupLocations.RITA, 8),
        (PickupLocations.INNOVATION, 1),
    ],
    PickupLocations.RITA: [
        (PickupLocations.WARREN_EQL, 8),
        (PickupLocations.INNOVATION, 7),
        (PickupLocations.EIGHTH, 4),
    ],
    PickupLocations.INNOVATION: [(PickupLocations.WARREN_EQL, 1), (PickupLocations.RITA, 7)],
    PickupLocations.EIGHTH: [(PickupLocations.RITA, 4), (PickupLocations.MUIR, 2)],
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
