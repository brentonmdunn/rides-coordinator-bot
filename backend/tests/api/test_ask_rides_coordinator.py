"""Integration tests for /api/ask-rides/coordinator routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.ask_rides_coordinator import router as coordinator_router
from bot.services.ride_coordinator_service import UserLookupStatus


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(coordinator_router)
    app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"
    return TestClient(app)


VALID_ID = "123456789012345678"


class TestGetCoordinator:
    def test_returns_not_configured_when_unset(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides_coordinator.RideCoordinatorService.get_coordinator_id",
            new=AsyncMock(return_value=None),
        ):
            resp = client.get("/api/ask-rides/coordinator")

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False
        assert body["user_id"] is None

    def test_returns_username_when_bot_ready(self):
        client = _build_client()
        fake_bot = MagicMock()
        fake_bot.is_ready.return_value = True
        fake_user = MagicMock()
        fake_user.name = "coolcoordinator"
        fake_user.display_name = "Cool Coordinator"

        with (
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.get_coordinator_id",
                new=AsyncMock(return_value=VALID_ID),
            ),
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=fake_bot),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.try_resolve_discord_user",
                new=AsyncMock(return_value=(UserLookupStatus.VERIFIED, fake_user)),
            ),
        ):
            resp = client.get("/api/ask-rides/coordinator")

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["username"] == "coolcoordinator"

    def test_returns_configured_without_username_when_bot_not_ready(self):
        client = _build_client()

        with (
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.get_coordinator_id",
                new=AsyncMock(return_value=VALID_ID),
            ),
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=None),
        ):
            resp = client.get("/api/ask-rides/coordinator")

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert "username" not in body


class TestSetCoordinator:
    def test_rejects_non_snowflake(self):
        client = _build_client()

        with patch("api.routes.ask_rides_coordinator.get_bot", return_value=None):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": "not-a-snowflake"})

        assert resp.status_code == 422

    def test_rejects_bots_own_id(self):
        client = _build_client()
        fake_bot = MagicMock()
        fake_bot.user.id = int(VALID_ID)

        with patch("api.routes.ask_rides_coordinator.get_bot", return_value=fake_bot):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": VALID_ID})

        assert resp.status_code == 422
        assert "bot" in resp.json()["detail"].lower()

    def test_rejects_when_discord_user_not_found(self):
        client = _build_client()
        fake_bot = MagicMock()
        fake_bot.is_ready.return_value = True
        fake_bot.user.id = 999999999999999999

        with (
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=fake_bot),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.try_resolve_discord_user",
                new=AsyncMock(return_value=(UserLookupStatus.NOT_FOUND, None)),
            ),
        ):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": VALID_ID})

        assert resp.status_code == 422
        assert "no discord user" in resp.json()["detail"].lower()

    def test_saves_with_warning_when_verification_unavailable(self):
        client = _build_client()
        fake_bot = MagicMock()
        fake_bot.is_ready.return_value = True
        fake_bot.user.id = 999999999999999999

        with (
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=fake_bot),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.try_resolve_discord_user",
                new=AsyncMock(return_value=(UserLookupStatus.UNAVAILABLE, None)),
            ),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.set_coordinator_id",
                new=AsyncMock(),
            ) as mock_set,
        ):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": VALID_ID})

        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert "warning" in body
        mock_set.assert_awaited_once_with(VALID_ID)

    def test_saves_with_warning_when_bot_not_ready(self):
        client = _build_client()

        with (
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=None),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.set_coordinator_id",
                new=AsyncMock(),
            ) as mock_set,
        ):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": VALID_ID})

        assert resp.status_code == 200
        body = resp.json()
        assert "warning" in body
        mock_set.assert_awaited_once_with(VALID_ID)

    def test_saves_with_username_when_verified(self):
        client = _build_client()
        fake_bot = MagicMock()
        fake_bot.is_ready.return_value = True
        fake_bot.user.id = 999999999999999999
        fake_user = MagicMock()
        fake_user.name = "coolcoordinator"

        with (
            patch("api.routes.ask_rides_coordinator.get_bot", return_value=fake_bot),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.try_resolve_discord_user",
                new=AsyncMock(return_value=(UserLookupStatus.VERIFIED, fake_user)),
            ),
            patch(
                "api.routes.ask_rides_coordinator.RideCoordinatorService.set_coordinator_id",
                new=AsyncMock(),
            ),
        ):
            resp = client.put("/api/ask-rides/coordinator", json={"user_id": VALID_ID})

        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "coolcoordinator"
        assert "warning" not in body
