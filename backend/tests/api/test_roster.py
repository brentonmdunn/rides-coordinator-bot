"""Integration tests for /api/roster routes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.roster import router
from ridebot.services.roster_service import Person
from ridebot.utils.custom_exceptions import (
    RosterConflictError,
    RosterNotFoundError,
    RosterValidationError,
)

SERVICE = "api.routes.roster.RosterService"


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
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
    }
    return Person(**(base | overrides))


class TestAuth:
    def test_forbidden_role_rejected(self):
        client = _build_client(forbidden=True)
        assert client.get("/api/roster").status_code == 403

    def test_mutations_forbidden(self):
        client = _build_client(forbidden=True)
        assert client.delete("/api/roster/1").status_code == 403


class TestListRoster:
    def test_returns_people(self):
        client = _build_client()
        with patch(f"{SERVICE}.list_people", new=AsyncMock(return_value=[_person()])):
            resp = client.get("/api/roster")

        assert resp.status_code == 200
        body = resp.json()
        assert body["people"][0]["name"] == "Alice"
        assert body["people"][0]["discord_user_id"] == "123456789"
        assert body["people"][0]["updated_at"] == "2024-01-01T00:00:00+00:00"

    def test_null_updated_at(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(updated_at=None)]),
        ):
            resp = client.get("/api/roster")

        assert resp.status_code == 200
        assert resp.json()["people"][0]["updated_at"] is None

    def test_naive_updated_at_gets_utc_offset(self):
        """SQLite drops tzinfo, but the browser parses an offset-less string as local time."""
        client = _build_client()
        with patch(
            f"{SERVICE}.list_people",
            new=AsyncMock(return_value=[_person(updated_at=datetime(2024, 1, 1, 22, 30))]),
        ):
            resp = client.get("/api/roster")

        assert resp.json()["people"][0]["updated_at"] == "2024-01-01T22:30:00+00:00"


class TestOptions:
    def test_returns_options(self):
        client = _build_client()
        options = {"years": ["Freshman", "Sophomore"], "locations": ["Muir"]}
        with patch(f"{SERVICE}.get_options", return_value=options):
            resp = client.get("/api/roster/options")

        assert resp.status_code == 200
        assert resp.json() == options

    def test_not_captured_by_person_id_route(self):
        client = _build_client()
        options = {"years": [], "locations": []}
        with (
            patch(f"{SERVICE}.get_options", return_value=options) as mock_options,
            patch(f"{SERVICE}.get_person", new=AsyncMock()) as mock_get_person,
        ):
            resp = client.get("/api/roster/options")

        assert resp.status_code == 200
        mock_options.assert_called_once()
        mock_get_person.assert_not_called()


class TestCreatePerson:
    def test_create_success(self):
        client = _build_client()
        with patch(f"{SERVICE}.create_person", new=AsyncMock(return_value=_person())):
            resp = client.post(
                "/api/roster",
                json={"name": "Alice", "discord_username": "alice"},
            )

        assert resp.status_code == 201
        assert resp.json()["name"] == "Alice"

    def test_validation_error_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person",
            new=AsyncMock(side_effect=RosterValidationError("name is required")),
        ):
            resp = client.post("/api/roster", json={"name": ""})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "name is required"

    def test_conflict_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.create_person",
            new=AsyncMock(side_effect=RosterConflictError("username taken")),
        ):
            resp = client.post("/api/roster", json={"name": "Alice"})
        assert resp.status_code == 409

    def test_missing_name_422(self):
        client = _build_client()
        resp = client.post("/api/roster", json={})
        assert resp.status_code == 422

    def test_unexpected_error_500(self):
        client = _build_client()
        with patch(f"{SERVICE}.create_person", new=AsyncMock(side_effect=RuntimeError("boom"))):
            resp = client.post("/api/roster", json={"name": "Alice"})
        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"


class TestUpdatePerson:
    def test_update_success(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person", new=AsyncMock(return_value=_person(name="Bob"))
        ) as mock_update:
            resp = client.patch("/api/roster/1", json={"name": "Bob"})

        assert resp.status_code == 200
        assert resp.json()["name"] == "Bob"
        assert mock_update.call_args.args == (1, {"name": "Bob"})

    def test_not_found_404(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=RosterNotFoundError("no such person")),
        ):
            resp = client.patch("/api/roster/999", json={"name": "Bob"})
        assert resp.status_code == 404

    def test_validation_error_400(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=RosterValidationError("bad year")),
        ):
            resp = client.patch("/api/roster/1", json={"year": "nope"})
        assert resp.status_code == 400

    def test_conflict_409(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.update_person",
            new=AsyncMock(side_effect=RosterConflictError("username taken")),
        ):
            resp = client.patch("/api/roster/1", json={"discord_username": "bob"})
        assert resp.status_code == 409


class TestDeletePerson:
    def test_delete_success(self):
        client = _build_client()
        with (
            patch(f"{SERVICE}.get_person", new=AsyncMock(return_value=_person())),
            patch(f"{SERVICE}.delete_people", new=AsyncMock(return_value=1)) as mock_delete,
        ):
            resp = client.delete("/api/roster/1")

        assert resp.status_code == 204
        mock_delete.assert_awaited_once_with([1])

    def test_delete_unknown_404(self):
        client = _build_client()
        with patch(
            f"{SERVICE}.get_person",
            new=AsyncMock(side_effect=RosterNotFoundError("no such person")),
        ):
            resp = client.delete("/api/roster/999")
        assert resp.status_code == 404


class TestBulkDelete:
    def test_bulk_delete_success(self):
        client = _build_client()
        with patch(f"{SERVICE}.delete_people", new=AsyncMock(return_value=2)):
            resp = client.post("/api/roster/bulk-delete", json={"ids": [1, 2]})

        assert resp.status_code == 200
        assert resp.json() == {"deleted": 2}

    def test_empty_ids_422(self):
        client = _build_client()
        resp = client.post("/api/roster/bulk-delete", json={"ids": []})
        assert resp.status_code == 422

    def test_too_many_ids_422(self):
        client = _build_client()
        resp = client.post("/api/roster/bulk-delete", json={"ids": list(range(501))})
        assert resp.status_code == 422
