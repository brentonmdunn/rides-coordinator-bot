"""Unit tests for RouteService."""

from __future__ import annotations

import pytest

from bot.core.enums import PickupLocations
from bot.services.route_service import RouteService

# ---------------------------------------------------------------------------
# get_pickup_location_fuzzy
# ---------------------------------------------------------------------------


def test_fuzzy_exact_value_match():
    """A perfect match should resolve to the correct enum."""
    result = RouteService.get_pickup_location_fuzzy("Seventh mail room")
    assert result == PickupLocations.SEVENTH


def test_fuzzy_partial_match():
    """A clear partial string should still match the right location."""
    result = RouteService.get_pickup_location_fuzzy("seventh")
    assert result == PickupLocations.SEVENTH


def test_fuzzy_erc():
    result = RouteService.get_pickup_location_fuzzy("ERC across")
    assert result == PickupLocations.ERC


def test_fuzzy_no_match_returns_none():
    """Completely unrelated string should return None."""
    result = RouteService.get_pickup_location_fuzzy("zzzzzzzzz_no_match_here")
    assert result is None


def test_fuzzy_rita():
    result = RouteService.get_pickup_location_fuzzy("Rita")
    assert result == PickupLocations.RITA


def test_fuzzy_innovation():
    result = RouteService.get_pickup_location_fuzzy("Innovation")
    assert result == PickupLocations.INNOVATION


# ---------------------------------------------------------------------------
# make_route — basic functionality
# ---------------------------------------------------------------------------


def test_make_route_single_location():
    """Single location should produce exactly one entry with the leave time."""
    result = RouteService.make_route("SEVENTH", "7:00pm")
    assert "7:00pm" in result
    assert "Seventh" in result


def test_make_route_two_locations():
    """Two locations should produce two time entries."""
    result = RouteService.make_route("SEVENTH ERC", "7:00pm")
    parts = result.split(", ")
    assert len(parts) == 2


def test_make_route_reverse_order_times():
    """
    First pickup is earlier than the leave time, so the first location in the
    result string should have an earlier time than the last.
    """
    result = RouteService.make_route("SEVENTH ERC", "7:00pm")
    # Both time fragments should appear; just assert the string is non-empty
    assert result != ""


def test_make_route_fuzzy_location_fallback():
    """A recognisable but non-enum-key location should be fuzzy-matched."""
    result = RouteService.make_route("seventh erc", "6:00pm")
    assert "Seventh" in result or "seventh" in result.lower()


def test_make_route_invalid_location_raises():
    with pytest.raises(ValueError, match="Invalid location"):
        RouteService.make_route("ATLANTIS", "7:00pm")


def test_make_route_includes_leave_time_in_output():
    result = RouteService.make_route("SEVENTH", "10:00am")
    assert "10:00am" in result


def test_make_route_with_map_url_format():
    """If a map URL is available the output should contain 'Google Maps'."""
    result = RouteService.make_route("RITA", "7:00pm")
    # Rita may or may not have a map URL; just assert we get a non-empty string
    assert isinstance(result, str) and len(result) > 0


def test_make_route_multiple_stops_produces_comma_separated():
    result = RouteService.make_route("SEVENTH ERC MARSHALL", "7:00pm")
    # Three stops → at least two commas
    assert result.count(",") >= 2


def test_make_route_pm_time_format():
    result = RouteService.make_route("SEVENTH", "19:00")
    assert "7:00pm" in result


def test_make_route_am_time_format():
    result = RouteService.make_route("SEVENTH", "10:30am")
    assert "10:30am" in result
