"""Unit tests for bot.utils.locations (Dijkstra lookup_time + LOCATIONS_MATRIX)."""

from bot.core.enums import PickupLocations
from bot.core.schemas import LocationQuery
from bot.utils.locations import LOCATIONS_MATRIX, lookup_time


class TestLocationsMatrix:
    """Sanity checks on the LOCATIONS_MATRIX graph structure."""

    def test_matrix_contains_start_and_end(self):
        assert "START" in LOCATIONS_MATRIX
        assert "END" in LOCATIONS_MATRIX

    def test_all_pickup_locations_present(self):
        expected = {
            PickupLocations.MUIR,
            PickupLocations.SIXTH,
            PickupLocations.MARSHALL,
            PickupLocations.ERC,
            PickupLocations.SEVENTH,
            PickupLocations.WARREN_EQL,
            PickupLocations.GEISEL_LOOP,
            PickupLocations.RITA,
            PickupLocations.INNOVATION,
            PickupLocations.EIGHTH,
            PickupLocations.PCYN_LOOP,
        }
        for loc in expected:
            assert loc in LOCATIONS_MATRIX, f"{loc} missing from LOCATIONS_MATRIX"

    def test_all_edges_have_positive_weights(self):
        for node, edges in LOCATIONS_MATRIX.items():
            for neighbor, weight in edges:
                assert weight > 0, f"Edge {node} -> {neighbor} has non-positive weight {weight}"

    def test_graph_is_bidirectional_for_campus_nodes(self):
        """Every campus-to-campus edge should have a reverse edge."""
        campus_nodes = {k for k in LOCATIONS_MATRIX if k not in ("START", "END")}
        for node in campus_nodes:
            for neighbor, _ in LOCATIONS_MATRIX[node]:
                if neighbor in campus_nodes:
                    reverse_neighbors = [n for n, _ in LOCATIONS_MATRIX[neighbor]]
                    assert node in reverse_neighbors, (
                        f"Edge {node} -> {neighbor} has no reverse edge"
                    )


class TestLookupTime:
    """Tests for the Dijkstra-based lookup_time function."""

    def test_adjacent_locations(self):
        query = LocationQuery(
            start_location=PickupLocations.MUIR,
            end_location=PickupLocations.SIXTH,
        )
        assert lookup_time(query) == 1

    def test_same_location_returns_zero(self):
        query = LocationQuery(
            start_location=PickupLocations.MUIR,
            end_location=PickupLocations.MUIR,
        )
        assert lookup_time(query) == 0

    def test_multi_hop_route(self):
        query = LocationQuery(
            start_location=PickupLocations.MUIR,
            end_location=PickupLocations.ERC,
        )
        result = lookup_time(query)
        # Muir -> Sixth (1) -> Marshall (1) -> ERC (1) = 3
        assert result == 3

    def test_reverse_route_symmetry(self):
        fwd = lookup_time(
            LocationQuery(
                start_location=PickupLocations.SIXTH,
                end_location=PickupLocations.ERC,
            )
        )
        rev = lookup_time(
            LocationQuery(
                start_location=PickupLocations.ERC,
                end_location=PickupLocations.SIXTH,
            )
        )
        assert fwd == rev

    def test_longer_route(self):
        query = LocationQuery(
            start_location=PickupLocations.MUIR,
            end_location=PickupLocations.SEVENTH,
        )
        result = lookup_time(query)
        # Muir -> Sixth (1) -> Marshall (1) -> ERC (1) -> Seventh (1) = 4
        assert result == 4

    def test_all_pairs_return_nonneg(self):
        """Every pair of campus locations should return a non-negative travel time."""
        campus = [loc for loc in LOCATIONS_MATRIX if loc not in ("START", "END")]
        for src in campus:
            for dst in campus:
                if isinstance(src, PickupLocations) and isinstance(dst, PickupLocations):
                    result = lookup_time(LocationQuery(start_location=src, end_location=dst))
                    assert result >= 0, f"Negative time from {src} to {dst}"

    def test_triangle_inequality(self):
        """Travel via an intermediate should never be shorter than direct."""
        a, b, c = PickupLocations.MUIR, PickupLocations.SIXTH, PickupLocations.MARSHALL
        ab = lookup_time(LocationQuery(start_location=a, end_location=b))
        bc = lookup_time(LocationQuery(start_location=b, end_location=c))
        ac = lookup_time(LocationQuery(start_location=a, end_location=c))
        assert ac <= ab + bc
