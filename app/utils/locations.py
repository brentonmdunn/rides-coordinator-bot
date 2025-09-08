from app.core.schemas import LocationQuery

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
    # Use the value of the enum member to access the dictionary
    for neighbor, time in LOCATIONS_MATRIX[query.start_location.value]:
        if neighbor == query.end_location.value:
            return time