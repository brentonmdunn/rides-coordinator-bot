"""Integration tests for /api/pickup-locations routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.pickup_locations import router

SERVICE = "api.routes.pickup_locations.PickupLocationsService"


def _build_client(*, forbidden: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    if forbidden:

        def _raise_forbidden():
            raise HTTPException(status_code=403, detail="Forbidden")

        app.dependency_overrides[require_ride_coordinator] = _raise_forbidden
    else:
        app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"

    return TestClient(app)


def _location(**overrides) -> dict:
    base = {
        "id": 1,
        "name": "Alpha",
        "latitude": 32.88,
        "longitude": -117.24,
        "minutes_from_start": None,
        "minutes_to_end": None,
        "is_active": True,
        "is_seeded": False,
    }
    return base | overrides


def _payload() -> dict:
    return {
        "locations": [_location()],
        "edges": [{"id": 5, "location_a_id": 1, "location_b_id": 2, "minutes": 4}],
        "living_mappings": [{"living_location": "Muir", "pickup_location_id": 1}],
        "pickup_adjustment": 1,
        "unreachable": ["Alpha"],
    }


class TestAuth:
    def test_forbidden_role_rejected(self):
        client = _build_client(forbidden=True)
        assert client.get("/api/pickup-locations").status_code == 403

    def test_mutations_forbidden(self):
        client = _build_client(forbidden=True)
        assert client.delete("/api/pickup-locations/1").status_code == 403


class TestGetPayload:
    def test_returns_full_payload(self):
        client = _build_client()
        with patch(f"{SERVICE}.get_all", new=AsyncMock(return_value=_payload())):
            resp = client.get("/api/pickup-locations")

        assert resp.status_code == 200
        body = resp.json()
        assert body["locations"][0]["name"] == "Alpha"
        assert body["edges"][0]["minutes"] == 4
        assert body["pickup_adjustment"] == 1
        assert body["unreachable"] == ["Alpha"]


class TestCreateLocation:
    def test_create_success(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_location", new=AsyncMock(return_value=_location())
        ) as mock_create:
            resp = client.post(
                "/api/pickup-locations",
                json={"name": "  Alpha  ", "latitude": 32.88, "longitude": -117.24},
            )

        assert resp.status_code == 201
        assert resp.json()["name"] == "Alpha"
        # Name is trimmed before hitting the service
        assert mock_create.call_args.kwargs["name"] == "Alpha"

    def test_duplicate_name_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_location",
            new=AsyncMock(side_effect=ValueError("already exists")),
        ):
            resp = client.post(
                "/api/pickup-locations",
                json={"name": "Alpha", "latitude": 32.88, "longitude": -117.24},
            )
        assert resp.status_code == 409

    def test_invalid_latitude_422(self):
        client = _build_client()
        resp = client.post(
            "/api/pickup-locations",
            json={"name": "Alpha", "latitude": 123.0, "longitude": -117.24},
        )
        assert resp.status_code == 422

    def test_blank_name_422(self):
        client = _build_client()
        resp = client.post(
            "/api/pickup-locations",
            json={"name": "   ", "latitude": 32.88, "longitude": -117.24},
        )
        assert resp.status_code == 422

    def test_nonpositive_minutes_422(self):
        client = _build_client()
        resp = client.post(
            "/api/pickup-locations",
            json={
                "name": "Alpha",
                "latitude": 32.88,
                "longitude": -117.24,
                "minutes_from_start": 0,
            },
        )
        assert resp.status_code == 422


class TestUpdateLocation:
    def test_update_success(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_location",
            new=AsyncMock(return_value=_location(is_active=False)),
        ) as mock_update:
            resp = client.patch("/api/pickup-locations/1", json={"is_active": False})

        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert mock_update.call_args.kwargs == {"is_active": False}

    def test_unknown_id_404(self):
        client = _build_client()
        with patch(f"{SERVICE}.update_location", new=AsyncMock(return_value=None)):
            resp = client.patch("/api/pickup-locations/999", json={"latitude": 33.0})
        assert resp.status_code == 404

    def test_rename_conflict_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_location",
            new=AsyncMock(side_effect=ValueError("already exists")),
        ):
            resp = client.patch("/api/pickup-locations/1", json={"name": "Beta"})
        assert resp.status_code == 409


class TestDeleteLocation:
    def test_delete_success(self):
        client = _build_client()
        with patch(f"{SERVICE}.soft_delete_location", new=AsyncMock(return_value=True)):
            resp = client.delete("/api/pickup-locations/1")
        assert resp.status_code == 204

    def test_delete_unknown_404(self):
        client = _build_client()
        with patch(f"{SERVICE}.soft_delete_location", new=AsyncMock(return_value=False)):
            resp = client.delete("/api/pickup-locations/999")
        assert resp.status_code == 404

    def test_delete_mapped_409_names_living_locations(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.soft_delete_location",
            new=AsyncMock(side_effect=ValueError("still mapped to it: Muir, Revelle")),
        ):
            resp = client.delete("/api/pickup-locations/1")
        assert resp.status_code == 409
        assert "Muir" in resp.json()["detail"]


class TestEdges:
    def test_upsert_edge_success(self):
        client = _build_client()
        edge = {"id": 5, "location_a_id": 1, "location_b_id": 2, "minutes": 4}
        with patch(f"{SERVICE}.upsert_edge", new=AsyncMock(return_value=edge)):
            resp = client.put(
                "/api/pickup-locations/edges",
                json={"location_a_id": 2, "location_b_id": 1, "minutes": 4},
            )
        assert resp.status_code == 200
        assert resp.json() == edge

    def test_self_edge_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.upsert_edge",
            new=AsyncMock(side_effect=ValueError("different locations")),
        ):
            resp = client.put(
                "/api/pickup-locations/edges",
                json={"location_a_id": 1, "location_b_id": 1, "minutes": 4},
            )
        assert resp.status_code == 400

    def test_zero_minutes_422(self):
        client = _build_client()
        resp = client.put(
            "/api/pickup-locations/edges",
            json={"location_a_id": 1, "location_b_id": 2, "minutes": 0},
        )
        assert resp.status_code == 422

    def test_delete_edge_404(self):
        client = _build_client()
        with patch(f"{SERVICE}.delete_edge", new=AsyncMock(return_value=False)):
            resp = client.delete("/api/pickup-locations/edges/999")
        assert resp.status_code == 404


class TestLivingMappings:
    def test_set_mapping_success(self):
        client = _build_client()
        mapping = {"living_location": "Muir", "pickup_location_id": 2}
        with patch(f"{SERVICE}.set_living_mapping", new=AsyncMock(return_value=mapping)):
            resp = client.put(
                "/api/pickup-locations/living-mappings/Muir",
                json={"pickup_location_id": 2},
            )
        assert resp.status_code == 200
        assert resp.json() == mapping

    def test_invalid_living_location_404(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.set_living_mapping",
            new=AsyncMock(side_effect=ValueError("Unknown living location")),
        ):
            resp = client.put(
                "/api/pickup-locations/living-mappings/Atlantis",
                json={"pickup_location_id": 2},
            )
        assert resp.status_code == 404


class TestPickupAdjustment:
    def test_set_adjustment(self):
        client = _build_client()
        with patch(f"{SERVICE}.set_pickup_adjustment", new=AsyncMock(return_value=2)):
            resp = client.put("/api/pickup-locations/settings/pickup-adjustment", json={"value": 2})
        assert resp.status_code == 200
        assert resp.json() == {"value": 2}

    def test_negative_adjustment_422(self):
        client = _build_client()
        resp = client.put("/api/pickup-locations/settings/pickup-adjustment", json={"value": -1})
        assert resp.status_code == 422
