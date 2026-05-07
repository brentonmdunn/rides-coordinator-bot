"""Tests for the all-pairs shortest-path helpers used by the group rides prompt."""

from bot.core.enums import PickupLocations
from bot.utils.locations import (
    LOCATIONS_MATRIX,
    compute_all_pairs_shortest_paths,
    render_distance_markdown,
)


class TestComputeAllPairsShortestPaths:
    """Test suite for compute_all_pairs_shortest_paths."""

    def test_defaults_to_locations_matrix(self):
        """Running with no args should compute over the module-level matrix."""
        result = compute_all_pairs_shortest_paths()
        assert PickupLocations.MUIR in result
        # Known direct edge
        assert result[PickupLocations.MUIR][PickupLocations.SIXTH] == 1

    def test_diagonal_is_zero(self):
        """Each node should have a zero-distance path to itself."""
        result = compute_all_pairs_shortest_paths()
        for node in result:
            assert result[node][node] == 0

    def test_multi_hop_distance(self):
        """Distance across multiple hops should be the sum of the shortest edges."""
        result = compute_all_pairs_shortest_paths()
        # Muir -> Sixth (1) -> Marshall (1) -> ERC (1) -> Seventh (1) = 4
        assert result[PickupLocations.MUIR][PickupLocations.SEVENTH] == 4

    def test_start_end_reachable(self):
        """START and END should connect to campus nodes via the cheapest edges."""
        result = compute_all_pairs_shortest_paths()
        # START directly connects to EIGHTH with weight 10.
        assert result["START"][PickupLocations.EIGHTH] == 10
        # END directly connects to SEVENTH with weight 20.
        assert result["END"][PickupLocations.SEVENTH] == 20

    def test_custom_adjacency(self):
        """A trivial custom adjacency list should produce expected distances."""
        adj = {
            "A": [("B", 2)],
            "B": [("A", 2), ("C", 3)],
            "C": [("B", 3)],
        }
        result = compute_all_pairs_shortest_paths(adj)
        assert result["A"]["C"] == 5
        assert result["C"]["A"] == 5
        assert result["B"]["A"] == 2


class TestRenderDistanceMarkdown:
    """Test suite for render_distance_markdown."""

    def test_contains_markdown_table_markers(self):
        """Output must look like a Markdown table."""
        md = render_distance_markdown()
        lines = md.splitlines()
        assert lines[0].startswith("|")
        assert lines[1].startswith("| ---")
        assert lines[0].endswith("|")

    def test_contains_start_and_end(self):
        """START and END should appear as both rows and columns."""
        md = render_distance_markdown()
        header = md.splitlines()[0]
        assert "START" in header
        assert "END" in header
        row_labels = [line.split("|")[1].strip() for line in md.splitlines()[2:]]
        assert "START" in row_labels
        assert "END" in row_labels

    def test_diagonal_renders_zero(self):
        """All self-distance cells render as the literal '0'."""
        md = render_distance_markdown()
        lines = md.splitlines()
        header_cells = [c.strip() for c in lines[0].split("|")[1:-1]]
        for row in lines[2:]:
            cells = [c.strip() for c in row.split("|")[1:-1]]
            row_label = cells[0]
            # skip the first header column ("from / to")
            for col_label, cell in zip(header_cells[1:], cells[1:], strict=True):
                if row_label == col_label:
                    assert cell == "0", f"diagonal cell {row_label} was {cell!r}"

    def test_known_distance_present(self):
        """A well-known short path should appear with the expected value."""
        md = render_distance_markdown()
        # Muir -> Seventh = 4 (Muir-Sixth-Marshall-ERC-Seventh, all weight 1)
        lines = md.splitlines()
        header = [c.strip() for c in lines[0].split("|")[1:-1]]
        seventh_col = header.index("Seventh")
        muir_row = next(row for row in lines[2:] if row.split("|")[1].strip() == "Muir")
        muir_cells = [c.strip() for c in muir_row.split("|")[1:-1]]
        assert muir_cells[seventh_col] == "4"

    def test_does_not_contain_enum_repr(self):
        """Rendered table must use short labels, not Python enum reprs."""
        md = render_distance_markdown()
        assert "PickupLocations." not in md
        assert "<" not in md

    def test_cached_result_is_stable(self):
        """Calling the default twice returns an identical string."""
        assert render_distance_markdown() == render_distance_markdown(LOCATIONS_MATRIX)
