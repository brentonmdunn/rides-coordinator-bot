"""Golden parity tests for the DB-backed routing graph.

The expected values below were computed with the pre-refactor hardcoded
implementation (bot/utils/locations.py lookup_time over LOCATIONS_MATRIX)
and frozen here. The DB-backed Dijkstra must reproduce them exactly.
"""

import pytest

from bot.services.pickup_locations_service import END_NODE, START_NODE
from tests.unit.routing_fixtures import make_seed_context

# All-pairs travel times from the old hardcoded LOCATIONS_MATRIX.
GOLDEN_PAIRS = {
    ("ERC across from bamboo", "Eighth basketball courts"): 5,
    ("ERC across from bamboo", "Geisel Loop"): 6,
    ("ERC across from bamboo", "Innovation"): 6,
    ("ERC across from bamboo", "Marshall uppers"): 1,
    ("ERC across from bamboo", "Muir tennis courts"): 3,
    ("ERC across from bamboo", "Pepper Canyon Loop"): 10,
    ("ERC across from bamboo", "Rita"): 9,
    ("ERC across from bamboo", "Seventh mail room"): 1,
    ("ERC across from bamboo", "Sixth loop"): 2,
    ("ERC across from bamboo", "Warren Equality Ln"): 5,
    ("Eighth basketball courts", "ERC across from bamboo"): 5,
    ("Eighth basketball courts", "Geisel Loop"): 11,
    ("Eighth basketball courts", "Innovation"): 11,
    ("Eighth basketball courts", "Marshall uppers"): 4,
    ("Eighth basketball courts", "Muir tennis courts"): 2,
    ("Eighth basketball courts", "Pepper Canyon Loop"): 5,
    ("Eighth basketball courts", "Rita"): 4,
    ("Eighth basketball courts", "Seventh mail room"): 6,
    ("Eighth basketball courts", "Sixth loop"): 3,
    ("Eighth basketball courts", "Warren Equality Ln"): 10,
    ("Geisel Loop", "ERC across from bamboo"): 6,
    ("Geisel Loop", "Eighth basketball courts"): 11,
    ("Geisel Loop", "Innovation"): 4,
    ("Geisel Loop", "Marshall uppers"): 7,
    ("Geisel Loop", "Muir tennis courts"): 9,
    ("Geisel Loop", "Pepper Canyon Loop"): 9,
    ("Geisel Loop", "Rita"): 11,
    ("Geisel Loop", "Seventh mail room"): 5,
    ("Geisel Loop", "Sixth loop"): 8,
    ("Geisel Loop", "Warren Equality Ln"): 3,
    ("Innovation", "ERC across from bamboo"): 6,
    ("Innovation", "Eighth basketball courts"): 11,
    ("Innovation", "Geisel Loop"): 4,
    ("Innovation", "Marshall uppers"): 7,
    ("Innovation", "Muir tennis courts"): 9,
    ("Innovation", "Pepper Canyon Loop"): 7,
    ("Innovation", "Rita"): 7,
    ("Innovation", "Seventh mail room"): 5,
    ("Innovation", "Sixth loop"): 8,
    ("Innovation", "Warren Equality Ln"): 1,
    ("Marshall uppers", "ERC across from bamboo"): 1,
    ("Marshall uppers", "Eighth basketball courts"): 4,
    ("Marshall uppers", "Geisel Loop"): 7,
    ("Marshall uppers", "Innovation"): 7,
    ("Marshall uppers", "Muir tennis courts"): 2,
    ("Marshall uppers", "Pepper Canyon Loop"): 9,
    ("Marshall uppers", "Rita"): 8,
    ("Marshall uppers", "Seventh mail room"): 2,
    ("Marshall uppers", "Sixth loop"): 1,
    ("Marshall uppers", "Warren Equality Ln"): 6,
    ("Muir tennis courts", "ERC across from bamboo"): 3,
    ("Muir tennis courts", "Eighth basketball courts"): 2,
    ("Muir tennis courts", "Geisel Loop"): 9,
    ("Muir tennis courts", "Innovation"): 9,
    ("Muir tennis courts", "Marshall uppers"): 2,
    ("Muir tennis courts", "Pepper Canyon Loop"): 7,
    ("Muir tennis courts", "Rita"): 6,
    ("Muir tennis courts", "Seventh mail room"): 4,
    ("Muir tennis courts", "Sixth loop"): 1,
    ("Muir tennis courts", "Warren Equality Ln"): 8,
    ("Pepper Canyon Loop", "ERC across from bamboo"): 10,
    ("Pepper Canyon Loop", "Eighth basketball courts"): 5,
    ("Pepper Canyon Loop", "Geisel Loop"): 9,
    ("Pepper Canyon Loop", "Innovation"): 7,
    ("Pepper Canyon Loop", "Marshall uppers"): 9,
    ("Pepper Canyon Loop", "Muir tennis courts"): 7,
    ("Pepper Canyon Loop", "Rita"): 9,
    ("Pepper Canyon Loop", "Seventh mail room"): 10,
    ("Pepper Canyon Loop", "Sixth loop"): 8,
    ("Pepper Canyon Loop", "Warren Equality Ln"): 6,
    ("Rita", "ERC across from bamboo"): 9,
    ("Rita", "Eighth basketball courts"): 4,
    ("Rita", "Geisel Loop"): 11,
    ("Rita", "Innovation"): 7,
    ("Rita", "Marshall uppers"): 8,
    ("Rita", "Muir tennis courts"): 6,
    ("Rita", "Pepper Canyon Loop"): 9,
    ("Rita", "Seventh mail room"): 10,
    ("Rita", "Sixth loop"): 7,
    ("Rita", "Warren Equality Ln"): 8,
    ("Seventh mail room", "ERC across from bamboo"): 1,
    ("Seventh mail room", "Eighth basketball courts"): 6,
    ("Seventh mail room", "Geisel Loop"): 5,
    ("Seventh mail room", "Innovation"): 5,
    ("Seventh mail room", "Marshall uppers"): 2,
    ("Seventh mail room", "Muir tennis courts"): 4,
    ("Seventh mail room", "Pepper Canyon Loop"): 10,
    ("Seventh mail room", "Rita"): 10,
    ("Seventh mail room", "Sixth loop"): 3,
    ("Seventh mail room", "Warren Equality Ln"): 4,
    ("Sixth loop", "ERC across from bamboo"): 2,
    ("Sixth loop", "Eighth basketball courts"): 3,
    ("Sixth loop", "Geisel Loop"): 8,
    ("Sixth loop", "Innovation"): 8,
    ("Sixth loop", "Marshall uppers"): 1,
    ("Sixth loop", "Muir tennis courts"): 1,
    ("Sixth loop", "Pepper Canyon Loop"): 8,
    ("Sixth loop", "Rita"): 7,
    ("Sixth loop", "Seventh mail room"): 3,
    ("Sixth loop", "Warren Equality Ln"): 7,
    ("Warren Equality Ln", "ERC across from bamboo"): 5,
    ("Warren Equality Ln", "Eighth basketball courts"): 10,
    ("Warren Equality Ln", "Geisel Loop"): 3,
    ("Warren Equality Ln", "Innovation"): 1,
    ("Warren Equality Ln", "Marshall uppers"): 6,
    ("Warren Equality Ln", "Muir tennis courts"): 8,
    ("Warren Equality Ln", "Pepper Canyon Loop"): 6,
    ("Warren Equality Ln", "Rita"): 8,
    ("Warren Equality Ln", "Seventh mail room"): 4,
    ("Warren Equality Ln", "Sixth loop"): 7,
}

# Travel times to/from the virtual START/END nodes in the old matrix.
GOLDEN_START_END = {
    (START_NODE, "Innovation"): 10,
    (START_NODE, "Eighth basketball courts"): 10,
    (START_NODE, "Rita"): 10,
    ("Seventh mail room", END_NODE): 20,
    ("Innovation", END_NODE): 20,
    ("Pepper Canyon Loop", END_NODE): 20,
    ("Muir tennis courts", END_NODE): 24,  # multi-hop through the graph
}


class TestGoldenParity:
    def test_all_pairs_match_old_implementation(self):
        ctx = make_seed_context()
        mismatches = [
            (start, end, expected, ctx.lookup_time(start, end))
            for (start, end), expected in GOLDEN_PAIRS.items()
            if ctx.lookup_time(start, end) != expected
        ]
        assert mismatches == []

    def test_start_end_times(self):
        ctx = make_seed_context()
        for (start, end), expected in GOLDEN_START_END.items():
            assert ctx.lookup_time(start, end) == expected, (start, end)

    def test_same_location_returns_zero(self):
        ctx = make_seed_context()
        assert ctx.lookup_time("Muir tennis courts", "Muir tennis courts") == 0

    def test_isolated_location_raises(self):
        ctx = make_seed_context()
        with pytest.raises(ValueError, match="No path found"):
            ctx.lookup_time("Warren Justice Ln", "Muir tennis courts")

    def test_unreachable_reports_isolated_location(self):
        ctx = make_seed_context()
        assert ctx.unreachable_names() == ["Warren Justice Ln"]
