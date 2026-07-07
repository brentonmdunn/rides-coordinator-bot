"""Unit tests for RoutingContext map helpers (formerly bot.utils.constants)."""

from tests.unit.routing_fixtures import make_seed_context


class TestMapUrl:
    """Tests for RoutingContext.map_url."""

    def test_known_location(self):
        ctx = make_seed_context()
        url = ctx.map_url("Sixth loop")
        assert url is not None
        assert "google.com/maps" in url
        assert "32.881096" in url
        assert "-117.24202" in url

    def test_returns_none_for_unknown_location(self):
        ctx = make_seed_context()
        assert ctx.map_url("Atlantis") is None

    def test_all_locations_return_urls(self):
        ctx = make_seed_context()
        for name in ctx.active_names:
            url = ctx.map_url(name)
            assert url is not None, f"map_url returned None for {name}"
            assert url.startswith("https://www.google.com/maps?q=")


class TestMapLinks:
    """Tests for RoutingContext.map_links."""

    def test_all_active_locations_present(self):
        ctx = make_seed_context()
        links = ctx.map_links()
        assert isinstance(links, dict)
        for name in ctx.active_names:
            assert name in links

    def test_values_are_urls(self):
        ctx = make_seed_context()
        for _name, url in ctx.map_links().items():
            assert "google.com/maps" in url


class TestCoordinates:
    """Tests for seeded coordinates."""

    def test_coordinates_are_in_san_diego(self):
        ctx = make_seed_context()
        for loc in ctx.locations:
            assert 32.8 < loc.latitude < 33.0, f"{loc.name} lat out of San Diego range"
            assert -117.3 < loc.longitude < -117.2, f"{loc.name} lng out of San Diego range"
