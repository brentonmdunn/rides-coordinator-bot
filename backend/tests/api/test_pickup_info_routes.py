"""Integration tests for /api/pickup-info routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.pickup_info import router
from ridebot.services.pickup_info_service import Person
from ridebot.utils.custom_exceptions import (
    PickupInfoConflictError,
    PickupInfoNotFoundError,
    PickupInfoValidationError,
)

SERVICE = "api.routes.pickup_info.PickupInfoService"


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


def _person(**overrides) -> Person:
    base = {
        "id": 1,
        "name": "Alice",
        "discord_username": "alice",
        "discord_user_id": "123456789",
        "year": "Freshman",
        "location": "Pepper Canyon West",
        "phone": "8585551234",
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    return Person(**(base | overrides))


class TestAuth:
    def test_forbidden_role_rejected(self):
        client = _build_client(forbidden=True)
        assert client.get("/api/pickup-info").status_code == 403

    def test_mutations_forbidden(self):
        client = _build_client(forbidden=True)
        assert client.delete("/api/pickup-info/1").status_code == 403


class TestListPickupInfo:
    def test_returns_people(self):
        client = _build_client()
        with patch(f"{SERVICE}.list_people", new=AsyncMock(return_value=[_person()])):
            resp = client.get("/api/pickup-info")

        assert resp.status_code == 200
        body = resp.json()
        assert body["people"][0]["name"] == "Alice"
        assert body["people"][0]["discord_user_id"] == "123456789"
        assert body["people"][0]["updated_at"] == "2024-01-01T00:00:00+00:00"
        assert body["people"][0]["phone"] == "8585551234"
        assert body["people"][0]["phone_display"] == "(858) 555-1234"
        assert body["people"][0]["phone_status"] == "ok"

    def test_invalid_phone_status(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(phone="123")]),
        ):
            resp = client.get("/api/pickup-info")

        assert resp.status_code == 200
        body = resp.json()["people"][0]
        assert body["phone"] == "123"
        assert body["phone_display"] == "123"
        assert body["phone_status"] == "invalid"

    def test_missing_phone_status(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(phone=None)]),
        ):
            resp = client.get("/api/pickup-info")

        assert resp.status_code == 200
        body = resp.json()["people"][0]
        assert body["phone"] is None
        assert body["phone_display"] is None
        assert body["phone_status"] == "missing"

    def test_null_updated_at(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(updated_at=None)]),
        ):
            resp = client.get("/api/pickup-info")

        assert resp.status_code == 200
        assert resp.json()["people"][0]["updated_at"] is None

    def test_naive_updated_at_gets_utc_offset(self):
        """SQLite drops tzinfo, but the browser parses an offset-less string as local time."""
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(updated_at=datetime(2024, 1, 1, 22, 30))]),
        ):
            resp = client.get("/api/pickup-info")

        assert resp.json()["people"][0]["updated_at"] == "2024-01-01T22:30:00+00:00"


class TestOptions:
    def test_returns_options(self):
        client = _build_client()
        options = {"years": ["Freshman", "Sophomore"], "locations": ["Muir"]}
        with patch(f"{SERVICE}.get_options", return_value=options):
            resp = client.get("/api/pickup-info/options")

        assert resp.status_code == 200
        assert resp.json() == options

    def test_not_captured_by_person_id_route(self):
        client = _build_client()
        options = {"years": [], "locations": []}
        with (
            patch(f"{SERVICE}.get_options", return_value=options) as mock_options,
            patch(f"{SERVICE}.get_person", new=AsyncMock()) as mock_get_person,
        ):
            resp = client.get("/api/pickup-info/options")

        assert resp.status_code == 200
        mock_options.assert_called_once()
        mock_get_person.assert_not_called()


class TestCreatePerson:
    def test_create_success(self):
        client = _build_client()
        with patch(f"{SERVICE}.create_person", new=AsyncMock(return_value=_person())):
            resp = client.post(
                "/api/pickup-info",
                json={"name": "Alice", "discord_username": "alice"},
            )

        assert resp.status_code == 201
        assert resp.json()["name"] == "Alice"

    def test_create_passes_phone_through(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person", new=AsyncMock(return_value=_person())
        ) as mock_create:
            resp = client.post(
                "/api/pickup-info",
                json={"name": "Alice", "phone": "858-555-1234"},
            )

        assert resp.status_code == 201
        assert mock_create.call_args.args[0].phone == "858-555-1234"

    def test_validation_error_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person",
            new=AsyncMock(side_effect=PickupInfoValidationError("name is required")),
        ):
            resp = client.post("/api/pickup-info", json={"name": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "name is required"

    def test_invalid_phone_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person",
            new=AsyncMock(
                side_effect=PickupInfoValidationError(
                    "Invalid phone number: 123. Use a 10-digit US number, e.g. (858) 555-1234"
                )
            ),
        ):
            resp = client.post("/api/pickup-info", json={"name": "Alice", "phone": "123"})
        assert resp.status_code == 400
        assert "Invalid phone number" in resp.json()["detail"]

    def test_conflict_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person",
            new=AsyncMock(side_effect=PickupInfoConflictError("username taken")),
        ):
            resp = client.post("/api/pickup-info", json={"name": "Alice"})
        assert resp.status_code == 409

    def test_missing_name_422(self):
        client = _build_client()
        resp = client.post("/api/pickup-info", json={})
        assert resp.status_code == 422

    def test_unexpected_error_500(self):
        client = _build_client()
        with patch(f"{SERVICE}.create_person", new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/pickup-info", json={"name": "Alice"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"


class TestUpdatePerson:
    def test_update_success(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person", new=AsyncMock(return_value=_person(name="Bob"))
        ) as mock_update:
            resp = client.patch("/api/pickup-info/1", json={"name": "Bob"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"
        assert mock_update.call_args.args == (1, {"name": "Bob"})

    def test_update_phone_passes_through(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(return_value=_person(phone="8585551234")),
        ) as mock_update:
            resp = client.patch("/api/pickup-info/1", json={"phone": "(858) 555-1234"})

        assert resp.status_code == 200
        assert mock_update.call_args.args == (1, {"phone": "(858) 555-1234"})
        assert resp.json()["phone_display"] == "(858) 555-1234"

    def test_update_blank_phone_clears(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(return_value=_person(phone=None)),
        ) as mock_update:
            resp = client.patch("/api/pickup-info/1", json={"phone": ""})

        assert resp.status_code == 200
        assert mock_update.call_args.args == (1, {"phone": ""})
        assert resp.json()["phone"] is None
        assert resp.json()["phone_status"] == "missing"

    def test_invalid_phone_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(
                side_effect=PickupInfoValidationError(
                    "Invalid phone number: 123. Use a 10-digit US number, e.g. (858) 555-1234"
                )
            ),
        ):
            resp = client.patch("/api/pickup-info/1", json={"phone": "123"})
        assert resp.status_code == 400
        assert "Invalid phone number" in resp.json()["detail"]

    def test_not_found_404(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=PickupInfoNotFoundError("no such person")),
        ):
            resp = client.patch("/api/pickup-info/999", json={"name": "Bob"})
        assert resp.status_code == 404

    def test_validation_error_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=PickupInfoValidationError("bad year")),
        ):
            resp = client.patch("/api/pickup-info/1", json={"year": "nope"})
        assert resp.status_code == 400

    def test_conflict_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=PickupInfoConflictError("username taken")),
        ):
            resp = client.patch("/api/pickup-info/1", json={"discord_username": "bob"})
        assert resp.status_code == 409


class TestDeletePerson:
    def test_delete_success(self):
        client = _build_client()
        with (
            patch(f"{SERVICE}.get_person", new=AsyncMock(return_value=_person())),
            patch(f"{SERVICE}.delete_people", new=AsyncMock(return_value=1)) as mock_delete,
        ):
            resp = client.delete("/api/pickup-info/1")

        assert resp.status_code == 204
        mock_delete.assert_awaited_once_with([1])

    def test_delete_unknown_404(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.get_person",
            new=AsyncMock(side_effect=PickupInfoNotFoundError("no such person")),
        ):
            resp = client.delete("/api/pickup-info/999")
        assert resp.status_code == 404


class TestBulkDelete:
    def test_bulk_delete_success(self):
        client = _build_client()
        with patch(f"{SERVICE}.delete_people", new=AsyncMock(return_value=2)):
            resp = client.post("/api/pickup-info/bulk-delete", json={"ids": [1, 2]})

        assert resp.status_code == 200
        assert resp.json() == {"deleted": 2}

    def test_empty_ids_422(self):
        client = _build_client()
        resp = client.post("/api/pickup-info/bulk-delete", json={"ids": []})
        assert resp.status_code == 422

    def test_too_many_ids_422(self):
        client = _build_client()
        resp = client.post("/api/pickup-info/bulk-delete", json={"ids": list(range(501))})
        assert resp.status_code == 422
