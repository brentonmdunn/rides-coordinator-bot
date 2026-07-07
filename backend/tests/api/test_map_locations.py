"""Integration tests for the ungated GET /api/map-locations route."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.route_builder import router
from bot.services.pickup_locations_service import EdgeInfo, LocationInfo, RoutingContext

SERVICE = "api.routes.route_builder.PickupLocationsService"


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _routing_context() -> RoutingContext:
    locations = (
        LocationInfo(
            id=1,
            name="Alpha",
            latitude=32.88,
            longitude=-117.24,
            minutes_from_start=None,
            minutes_to_end=None,
            is_active=True,
            is_seeded=True,
        ),
        LocationInfo(
            id=2,
            name="Bravo",
            latitude=32.87,
            longitude=-117.23,
            minutes_from_start=10,
            minutes_to_end=20,
            is_active=False,
            is_seeded=False,
        ),
    )
    edges: tuple[EdgeInfo, ...] = ()
    return RoutingContext(
        locations=locations,
        edges=edges,
        living_to_pickup={},
        pickup_adjustment=1,
    )


class TestGetMapLocations:
    def test_returns_active_locations_with_map_urls(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.get_routing_context",
            new=AsyncMock(return_value=_routing_context()),
        ):
            resp = client.get("/api/map-locations")

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "locations": [
                {
                    "name": "Alpha",
                    "latitude": 32.88,
                    "longitude": -117.24,
                    "map_url": "https://www.google.com/maps?q=32.88,-117.24",
                }
            ]
        }

    def test_no_role_dependency(self):
        """The route must not require the ride coordinator role."""
        routes = {route.path: route for route in router.routes}
        route = routes["/api/map-locations"]
        dependency_names = [dep.call.__name__ for dep in route.dependant.dependencies]
        assert "require_ride_coordinator" not in dependency_names
