"""utils/locations.py"""

import heapq
import logging
from functools import lru_cache

from bot.core.enums import PickupLocations
from bot.core.schemas import LocationQuery

logger = logging.getLogger(__name__)

# Node type: either a PickupLocations enum or one of the special "START"/"END" strings.
LocationNode = PickupLocations | str

# Short labels used when rendering the distance table for the LLM. Keeping columns
# narrow matters because the model pays per-token attention to each header.
_SHORT_LABELS: dict[LocationNode, str] = {
    PickupLocations.MUIR: "Muir",
    PickupLocations.SIXTH: "Sixth",
    PickupLocations.MARSHALL: "Marshall",
    PickupLocations.ERC: "ERC",
    PickupLocations.SEVENTH: "Seventh",
    PickupLocations.WARREN_EQL: "Warren",
    PickupLocations.GEISEL_LOOP: "GeiselLoop",
    PickupLocations.RITA: "Rita",
    PickupLocations.INNOVATION: "Innovation",
    PickupLocations.EIGHTH: "Eighth",
    PickupLocations.PCYN_LOOP: "PepperCyn",
    "START": "START",
    "END": "END",
}


def _short(node: LocationNode) -> str:
    """Return the short label for a node used in the distance table."""
    return _SHORT_LABELS.get(node, str(node))


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

    raise ValueError(f"No path found from {query.start_location} to {query.end_location}")


def compute_all_pairs_shortest_paths(
    adjacency: dict[LocationNode, list[tuple[LocationNode, int]]] | None = None,
) -> dict[LocationNode, dict[LocationNode, int]]:
    """
    Compute all-pairs shortest paths over the locations graph via repeated Dijkstra.

    Treats the graph as undirected for reachability: if an edge only appears in one
    direction in the adjacency list, the reverse direction is still searched via
    the forward edges of the other node.

    Args:
        adjacency: Adjacency list. Defaults to the module-level ``LOCATIONS_MATRIX``.

    Returns:
        A dict ``{src: {dst: distance}}``. Unreachable pairs are omitted.
    """
    graph = adjacency if adjacency is not None else LOCATIONS_MATRIX
    nodes = list(graph.keys())
    result: dict[LocationNode, dict[LocationNode, int]] = {}

    for src in nodes:
        distances: dict[LocationNode, float] = {n: float("inf") for n in nodes}
        distances[src] = 0
        pq: list[tuple[float, LocationNode]] = [(0, src)]

        while pq:
            current_distance, current = heapq.heappop(pq)
            if current_distance > distances[current]:
                continue
            for neighbor, weight in graph.get(current, []):
                new_dist = current_distance + weight
                if new_dist < distances.get(neighbor, float("inf")):
                    distances[neighbor] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor))

        result[src] = {n: int(d) for n, d in distances.items() if d != float("inf")}

    return result


@lru_cache(maxsize=1)
def _cached_all_pairs() -> dict[LocationNode, dict[LocationNode, int]]:
    """Cache the all-pairs table for the default ``LOCATIONS_MATRIX``."""
    return compute_all_pairs_shortest_paths(LOCATIONS_MATRIX)


# Node ordering used when rendering the table. Roughly groups by corridor so the
# human-readable output is easier to scan during debugging.
_TABLE_NODE_ORDER: list[LocationNode] = [
    "START",
    PickupLocations.MUIR,
    PickupLocations.SIXTH,
    PickupLocations.MARSHALL,
    PickupLocations.ERC,
    PickupLocations.SEVENTH,
    PickupLocations.EIGHTH,
    PickupLocations.RITA,
    PickupLocations.INNOVATION,
    PickupLocations.WARREN_EQL,
    PickupLocations.GEISEL_LOOP,
    PickupLocations.PCYN_LOOP,
    "END",
]


def render_distance_markdown(
    adjacency: dict[LocationNode, list[tuple[LocationNode, int]]] | None = None,
) -> str:
    """
    Render an all-pairs shortest-path distance table as a Markdown table.

    The cell ``row=A col=B`` is the minimum travel time (minutes) from A to B.
    Unreachable pairs render as ``-``. The diagonal renders as ``0``.

    Args:
        adjacency: Optional adjacency list. Defaults to ``LOCATIONS_MATRIX``.

    Returns:
        A Markdown table string suitable for inclusion in an LLM prompt.
    """
    if adjacency is None or adjacency is LOCATIONS_MATRIX:
        all_pairs = _cached_all_pairs()
    else:
        all_pairs = compute_all_pairs_shortest_paths(adjacency)

    nodes = [n for n in _TABLE_NODE_ORDER if n in all_pairs]
    # Append any nodes we forgot to order (future-proofing).
    for n in all_pairs:
        if n not in nodes:
            nodes.append(n)

    header = "| from / to | " + " | ".join(_short(n) for n in nodes) + " |"
    separator = "| --- | " + " | ".join("---" for _ in nodes) + " |"
    rows = [header, separator]

    for src in nodes:
        cells = []
        for dst in nodes:
            if src == dst:
                cells.append("0")
                continue
            d = all_pairs.get(src, {}).get(dst)
            cells.append(str(d) if d is not None else "-")
        rows.append(f"| {_short(src)} | " + " | ".join(cells) + " |")

    return "\n".join(rows)
