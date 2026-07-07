"""Unit tests for RouteService."""

from __future__ import annotations

import pytest

from bot.services.route_service import RouteService
from tests.unit.routing_fixtures import make_seed_context

CTX = make_seed_context()

# ---------------------------------------------------------------------------
# get_pickup_location_fuzzy
# ---------------------------------------------------------------------------


def test_fuzzy_exact_value_match():
    """A perfect match should resolve to the correct location name."""
    result = RouteService.get_pickup_location_fuzzy(CTX, "Seventh mail room")
    assert result == "Seventh mail room"


def test_fuzzy_partial_match():
    """A clear partial string should still match the right location."""
    result = RouteService.get_pickup_location_fuzzy(CTX, "seventh")
    assert result == "Seventh mail room"


def test_fuzzy_erc():
    result = RouteService.get_pickup_location_fuzzy(CTX, "ERC across")
    assert result == "ERC across from bamboo"


def test_fuzzy_no_match_returns_none():
    """Completely unrelated string should return None."""
    result = RouteService.get_pickup_location_fuzzy(CTX, "zzzzzzzzz_no_match_here")
    assert result is None


def test_fuzzy_rita():
    result = RouteService.get_pickup_location_fuzzy(CTX, "Rita")
    assert result == "Rita"


def test_fuzzy_innovation():
    result = RouteService.get_pickup_location_fuzzy(CTX, "Innovation")
    assert result == "Innovation"


# ---------------------------------------------------------------------------
# make_route — basic functionality
# ---------------------------------------------------------------------------


def test_make_route_single_location():
    """Single location should produce exactly one entry with the leave time."""
    result = RouteService.make_route(CTX, "seventh", "7:00pm")
    assert "7:00pm" in result
    assert "Seventh" in result


def test_make_route_two_locations():
    """Two locations should produce two time entries."""
    result = RouteService.make_route(CTX, "seventh erc", "7:00pm")
    parts = result.split(", ")
    assert len(parts) == 2


def test_make_route_from_names_full_names():
    """Full multi-word names must resolve exactly (API path)."""
    result = RouteService.make_route_from_names(
        CTX, ["Seventh mail room", "ERC across from bamboo"], "7:00pm"
    )
    assert "Seventh mail room" in result
    assert "ERC across from bamboo" in result


def test_make_route_fuzzy_location_fallback():
    """A recognisable but inexact location should be fuzzy-matched."""
    result = RouteService.make_route(CTX, "seventh erc", "6:00pm")
    assert "Seventh" in result or "seventh" in result.lower()


def test_make_route_invalid_location_raises():
    with pytest.raises(ValueError, match="Invalid location"):
        RouteService.make_route(CTX, "zzzzzzzzz_no_match_here", "7:00pm")


def test_make_route_includes_leave_time_in_output():
    result = RouteService.make_route(CTX, "seventh", "10:00am")
    assert "10:00am" in result


def test_make_route_travel_time_offsets():
    """Earlier stops get earlier times: Seventh->ERC is 1 min + 1 adjustment."""
    result = RouteService.make_route(CTX, "seventh erc", "7:00pm")
    # ERC is the last stop (7:00pm); Seventh is picked up 2 minutes earlier.
    assert "6:58pm" in result
    assert "7:00pm" in result


def test_make_route_with_map_url_format():
    """Seeded locations have coordinates, so output should contain a maps link."""
    result = RouteService.make_route(CTX, "rita", "7:00pm")
    assert "Google Maps" in result


def test_make_route_multiple_stops_produces_comma_separated():
    result = RouteService.make_route(CTX, "seventh erc marshall", "7:00pm")
    # Three stops → at least two commas
    assert result.count(",") >= 2


def test_make_route_pm_time_format():
    result = RouteService.make_route(CTX, "seventh", "19:00")
    assert "7:00pm" in result


def test_make_route_am_time_format():
    result = RouteService.make_route(CTX, "seventh", "10:30am")
    assert "10:30am" in result
