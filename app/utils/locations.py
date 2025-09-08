from app.core.schemas import LocationQuery
from app.core.logger import logger
import heapq
LOCATIONS_MATRIX = {
    "Muir": [("Sixth", 2), ("Eighth", 3)],
    "Sixth": [("Muir", 2), ("ERC", 2)],
    "ERC": [("Sixth", 2), ("Seventh", 2)],
    "Seventh": [("ERC", 2), ("Warren", 4)],
    "Warren": [("Seventh", 4), ("Rita", 8), ("Innovation", 2)],
    "Rita": [("Warren", 8), ("Innovation", 7), ("Eighth", 4)],
    "Innovation": [("Warren", 2), ("Rita", 7)],
    "Eighth": [("Rita", 4), ("Muir", 3)]
}

def lookup_time(query: LocationQuery) -> int:
    """
    Looks up the travel time between two locations using a Pydantic model for input.

    Args:
        query: A LocationQuery model containing the start and end locations.

    Returns:
        The travel time as an integer, or raises an exception if the path is not found.
    """
    logger.info(f"{query=}")
    distances = {location: float('inf') for location in LOCATIONS_MATRIX}
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