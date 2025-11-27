"""Tests for matching utility."""

from app.core.enums import PickupLocations
from app.utils.matching import get_pickup_location_fuzzy


class TestGetPickupLocationFuzzy:
    """Tests for the `get_pickup_location_fuzzy` function."""

    def test_exact_match(self):
        """Should return the exact enum member for an exact string match."""
        assert get_pickup_location_fuzzy("Sixth loop") == PickupLocations.SIXTH

    def test_case_insensitive_match(self):
        """Should match regardless of case."""
        assert get_pickup_location_fuzzy("sixth loop") == PickupLocations.SIXTH

    def test_partial_match_high_score(self):
        """Should match with high confidence partials."""
        assert get_pickup_location_fuzzy("Sixth") == PickupLocations.SIXTH

    def test_reordered_words(self):
        """Should match even if words are reordered (token sort)."""
        assert get_pickup_location_fuzzy("loop Sixth") == PickupLocations.SIXTH

    def test_typo_match(self):
        """Should match despite minor typos."""
        assert get_pickup_location_fuzzy("Sixt loop") == PickupLocations.SIXTH

    def test_fallback_match(self):
        """Should match using fallback mechanism for harder cases."""
        # "seveneth" -> "Seventh mail room"
        assert get_pickup_location_fuzzy("seveneth") == PickupLocations.SEVENTH

    def test_no_match(self):
        """Should return None for completely unrelated strings."""
        assert get_pickup_location_fuzzy("Xyzwq123") is None
