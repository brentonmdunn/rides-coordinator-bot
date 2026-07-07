"""Shared RoutingContext fixture data mirroring the seeded pickup locations.

The literals here are frozen copies of the Alembic seed (migration
44f6b5bdaeef), which itself froze the previously hardcoded constants.
"""

from bot.services.pickup_locations_service import (
    EdgeInfo,
    LocationInfo,
    RoutingContext,
    build_graph,
)

SEED_LOCATIONS = (
    # (id, name, latitude, longitude, minutes_from_start, minutes_to_end)
    (1, "Sixth loop", 32.881096, -117.242020, None, None),
    (2, "Seventh mail room", 32.888203, -117.242347, None, 20),
    (3, "Marshall uppers", 32.883187, -117.241281, None, None),
    (4, "ERC across from bamboo", 32.885294, -117.242357, None, None),
    (5, "Muir tennis courts", 32.878133, -117.243361, None, None),
    (6, "Eighth basketball courts", 32.873411, -117.242997, 10, None),
    (7, "Innovation", 32.879118, -117.231663, 10, 20),
    (8, "Rita", 32.873065, -117.235532, 10, None),
    (9, "Warren Equality Ln", 32.883587, -117.233687, None, None),
    (10, "Warren Justice Ln", 32.883156, -117.232222, None, None),
    (11, "Geisel Loop", 32.881598, -117.238614, None, None),
    (12, "Pepper Canyon Loop", 32.878366, -117.234230, 10, 20),
)

SEED_EDGES = (
    (1, 1, 3, 1),
    (2, 1, 5, 1),
    (3, 2, 4, 1),
    (4, 2, 9, 4),
    (5, 2, 11, 5),
    (6, 3, 4, 1),
    (7, 5, 6, 2),
    (8, 6, 8, 4),
    (9, 6, 12, 5),
    (10, 7, 8, 7),
    (11, 7, 9, 1),
    (12, 8, 9, 8),
    (13, 9, 11, 3),
    (14, 9, 12, 6),
)

SEED_LIVING_TO_PICKUP = {
    "Sixth": "Sixth loop",
    "Seventh": "Seventh mail room",
    "Marshall": "Marshall uppers",
    "ERC": "ERC across from bamboo",
    "Muir": "Muir tennis courts",
    "Eighth": "Eighth basketball courts",
    "Revelle": "Eighth basketball courts",
    "Pepper Canyon East": "Innovation",
    "Pepper Canyon West": "Innovation",
    "Rita": "Rita",
    "Warren": "Warren Equality Ln",
}


def make_seed_context(pickup_adjustment: int = 1) -> RoutingContext:
    """Build a RoutingContext equivalent to a freshly seeded database."""
    locations = tuple(
        LocationInfo(
            id=loc_id,
            name=name,
            latitude=lat,
            longitude=lng,
            minutes_from_start=from_start,
            minutes_to_end=to_end,
            is_active=True,
            is_seeded=True,
        )
        for loc_id, name, lat, lng, from_start, to_end in SEED_LOCATIONS
    )
    edges = tuple(
        EdgeInfo(id=edge_id, location_a_id=a, location_b_id=b, minutes=minutes)
        for edge_id, a, b, minutes in SEED_EDGES
    )
    return RoutingContext(
        locations=locations,
        edges=edges,
        living_to_pickup=dict(SEED_LIVING_TO_PICKUP),
        pickup_adjustment=pickup_adjustment,
        graph=build_graph(locations, edges),
    )
