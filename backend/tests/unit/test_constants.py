"""Unit tests for bot.utils.constants."""

from bot.core.enums import PickupLocations
from bot.utils.constants import MAP_LOCATIONS, get_map_links, get_map_url


class TestGetMapUrl:
    """Tests for get_map_url."""

    def test_known_location(self):
        url = get_map_url(PickupLocations.SIXTH)
        assert url is not None
        assert "google.com/maps" in url
        assert "32.881096" in url
        assert "-117.24202" in url

    def test_returns_none_for_unknown_location(self):
        url = get_map_url(PickupLocations.VILLAS_OF_RENAISSANCE)
        assert url is None

    def test_all_mapped_locations_return_urls(self):
        for loc in MAP_LOCATIONS:
            url = get_map_url(loc)
            assert url is not None, f"get_map_url returned None for {loc}"
            assert url.startswith("https://www.google.com/maps?q=")


class TestGetMapLinks:
    """Tests for get_map_links."""

    def test_returns_dict(self):
        links = get_map_links()
        assert isinstance(links, dict)

    def test_all_mapped_locations_present(self):
        links = get_map_links()
        for loc in MAP_LOCATIONS:
            assert loc in links

    def test_values_are_urls(self):
        links = get_map_links()
        for _loc, url in links.items():
            assert url is not None
            assert "google.com/maps" in url


class TestMapLocations:
    """Tests for the MAP_LOCATIONS constant."""

    def test_coordinates_are_in_san_diego(self):
        for loc, (lat, lng) in MAP_LOCATIONS.items():
            assert 32.8 < lat < 33.0, f"{loc} lat {lat} out of San Diego range"
            assert -117.3 < lng < -117.2, f"{loc} lng {lng} out of San Diego range"

    def test_coordinates_are_tuples(self):
        for _loc, coords in MAP_LOCATIONS.items():
            assert isinstance(coords, tuple)
            assert len(coords) == 2
