"""Integration tests for /api/drivers routes (permanent + temporary)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.drivers import router
from ridebot.services.temp_driver_service import (
    TempDriverEvent,
    TempDriverGrantInfo,
    TempDriverResult,
)

MODULE = "api.routes.drivers"


def _build_client(*, forbidden: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        request.state.user = {"email": "coordinator@example.com"}
        return await call_next(request)

    if forbidden:

        def _raise_forbidden():
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Forbidden")

        app.dependency_overrides[require_ride_coordinator] = _raise_forbidden
    else:
        app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"

    return TestClient(app)


def _fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.get_guild.return_value = MagicMock()
    return bot


def _bot_without_guild() -> MagicMock:
    bot = MagicMock()
    bot.get_guild.return_value = None
    return bot


def _grant_info(**overrides) -> TempDriverGrantInfo:
    base = {
        "discord_user_id": "111",
        "discord_username": "alice",
        "display_name": "Alice",
        "expires_at": datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC),
        "granted_by": "coordinator@example.com",
    }
    return TempDriverGrantInfo(**(base | overrides))


class TestAuth:
    def test_post_permanent_forbidden(self):
        client = _build_client(forbidden=True)
        resp = client.post("/api/drivers", json={"discord_username": "alice"})
        assert resp.status_code == 403

    def test_post_temp_forbidden(self):
        client = _build_client(forbidden=True)
        resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 403

    def test_delete_forbidden(self):
        client = _build_client(forbidden=True)
        resp = client.delete("/api/drivers/111")
        assert resp.status_code == 403

    def test_search_forbidden(self):
        client = _build_client(forbidden=True)
        resp = client.get("/api/drivers/search?q=al")
        assert resp.status_code == 403

    def test_list_allowed_without_coordinator_role(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.RoleManagementService.get_members", return_value=[]),
            patch(
                f"{MODULE}.TempDriverService.get_expiry_map",
                new=AsyncMock(return_value={}),
            ),
        ):
            resp = client.get("/api/drivers")
        assert resp.status_code == 200


class TestListDrivers:
    def test_returns_members_with_temp_expiry(self):
        client = _build_client()
        members = [
            {"discord_user_id": "111", "discord_username": "alice", "display_name": "Alice"},
            {"discord_user_id": "222", "discord_username": "bob", "display_name": "Bob"},
        ]
        expiry = {"111": datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC)}
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.RoleManagementService.get_members", return_value=members),
            patch(
                f"{MODULE}.TempDriverService.get_expiry_map",
                new=AsyncMock(return_value=expiry),
            ),
        ):
            resp = client.get("/api/drivers")

        assert resp.status_code == 200
        body = resp.json()["members"]
        alice = next(m for m in body if m["discord_user_id"] == "111")
        bob = next(m for m in body if m["discord_user_id"] == "222")
        assert alice["temp_expires_at"] == "2026-10-05T06:59:59+00:00"
        assert bob["temp_expires_at"] is None

    def test_bot_not_ready_503(self):
        client = _build_client()
        with patch(f"{MODULE}.get_bot", return_value=None):
            resp = client.get("/api/drivers")
        assert resp.status_code == 503


class TestAddPermanentDriver:
    def test_success_delegates_to_service(self):
        client = _build_client()
        member = {"discord_user_id": "111", "discord_username": "alice", "display_name": "Alice"}
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.add_permanent_driver",
                new=AsyncMock(return_value=member),
            ) as mock_add,
        ):
            resp = client.post("/api/drivers", json={"discord_username": "alice"})

        assert resp.status_code == 200
        assert resp.json() == member
        mock_add.assert_awaited_once_with("alice")

    def test_value_error_400(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.add_permanent_driver",
                new=AsyncMock(side_effect=ValueError("Member 'alice' not found in server")),
            ),
        ):
            resp = client.post("/api/drivers", json={"discord_username": "alice"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Member 'alice' not found in server"

    def test_guild_unavailable_503_without_calling_service(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_bot_without_guild()),
            patch(f"{MODULE}.TempDriverService.add_permanent_driver", new=AsyncMock()) as mock_add,
        ):
            resp = client.post("/api/drivers", json={"discord_username": "alice"})
        assert resp.status_code == 503
        mock_add.assert_not_awaited()

    def test_permission_error_403(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.add_permanent_driver",
                new=AsyncMock(side_effect=PermissionError("Bot lacks permission to assign roles")),
            ),
        ):
            resp = client.post("/api/drivers", json={"discord_username": "alice"})
        assert resp.status_code == 403

    def test_bot_not_ready_503(self):
        client = _build_client()
        with patch(f"{MODULE}.get_bot", return_value=None):
            resp = client.post("/api/drivers", json={"discord_username": "alice"})
        assert resp.status_code == 503


class TestAddTempDriver:
    def test_granted_response_shape(self):
        client = _build_client()
        grant = _grant_info()
        result = TempDriverResult(
            grant=grant,
            event=TempDriverEvent.GRANTED,
            previous_expires_at=None,
            announcement="announcement text",
        )
        fake_member = MagicMock()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.resolve_member", return_value=fake_member
            ) as mock_resolve,
            patch(
                f"{MODULE}.TempDriverService.grant", new=AsyncMock(return_value=result)
            ) as mock_grant,
        ):
            resp = client.post(
                "/api/drivers/temp", json={"discord_username": "alice", "duration": "3d"}
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "discord_user_id": "111",
            "discord_username": "alice",
            "display_name": "Alice",
            "expires_at": "2026-10-05T06:59:59+00:00",
            "previous_expires_at": None,
            "event": "granted",
        }
        mock_resolve.assert_called_once_with("alice")
        mock_grant.assert_awaited_once()
        args, kwargs = mock_grant.call_args
        assert args[0] is fake_member
        assert args[1] == "3d"
        assert args[2] == "coordinator@example.com"
        assert kwargs == {"announce": True}

    def test_extended_response_includes_previous_expiry(self):
        client = _build_client()
        grant = _grant_info(expires_at=datetime(2026, 11, 1, tzinfo=UTC))
        result = TempDriverResult(
            grant=grant,
            event=TempDriverEvent.EXTENDED,
            previous_expires_at=datetime(2026, 10, 5, 6, 59, 59, tzinfo=UTC),
            announcement="announcement text",
        )
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.TempDriverService.resolve_member", return_value=MagicMock()),
            patch(f"{MODULE}.TempDriverService.grant", new=AsyncMock(return_value=result)),
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["event"] == "extended"
        assert body["previous_expires_at"] == "2026-10-05T06:59:59+00:00"

    def test_duration_defaults_to_none(self):
        client = _build_client()
        result = TempDriverResult(
            grant=_grant_info(),
            event=TempDriverEvent.GRANTED,
            previous_expires_at=None,
            announcement="x",
        )
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.TempDriverService.resolve_member", return_value=MagicMock()),
            patch(
                f"{MODULE}.TempDriverService.grant", new=AsyncMock(return_value=result)
            ) as mock_grant,
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})

        assert resp.status_code == 200
        assert mock_grant.call_args.args[1] is None

    def test_resolve_member_not_found_400(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.resolve_member",
                side_effect=ValueError("Member 'alice' not found in server"),
            ),
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Member 'alice' not found in server"

    def test_grant_past_date_400(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.TempDriverService.resolve_member", return_value=MagicMock()),
            patch(
                f"{MODULE}.TempDriverService.grant",
                new=AsyncMock(side_effect=ValueError("That time is in the past.")),
            ),
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "That time is in the past."

    def test_guild_unavailable_503_without_calling_service(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_bot_without_guild()),
            patch(f"{MODULE}.TempDriverService.resolve_member") as mock_resolve,
            patch(f"{MODULE}.TempDriverService.grant", new=AsyncMock()) as mock_grant,
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 503
        mock_resolve.assert_not_called()
        mock_grant.assert_not_awaited()

    def test_permission_error_403(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(f"{MODULE}.TempDriverService.resolve_member", return_value=MagicMock()),
            patch(
                f"{MODULE}.TempDriverService.grant",
                new=AsyncMock(side_effect=PermissionError("Bot lacks permission to assign roles")),
            ),
        ):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 403

    def test_bot_not_ready_503(self):
        client = _build_client()
        with patch(f"{MODULE}.get_bot", return_value=None):
            resp = client.post("/api/drivers/temp", json={"discord_username": "alice"})
        assert resp.status_code == 503


class TestRemoveDriver:
    def test_success_ok_true(self):
        client = _build_client()
        member = {"discord_user_id": "111", "discord_username": "alice", "display_name": "Alice"}
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.remove_driver", new=AsyncMock(return_value=member)
            ) as mock_remove,
        ):
            resp = client.delete("/api/drivers/111")

        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        mock_remove.assert_awaited_once_with("111", "coordinator@example.com")

    def test_not_a_temp_driver_value_error_400(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.remove_driver",
                new=AsyncMock(
                    side_effect=ValueError(
                        "@alice isn't a temporary driver. Use the Drivers tab to remove "
                        "a permanent driver."
                    )
                ),
            ),
        ):
            resp = client.delete("/api/drivers/111")
        assert resp.status_code == 400

    def test_guild_unavailable_503_without_calling_service(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_bot_without_guild()),
            patch(f"{MODULE}.TempDriverService.remove_driver", new=AsyncMock()) as mock_remove,
        ):
            resp = client.delete("/api/drivers/111")
        assert resp.status_code == 503
        mock_remove.assert_not_awaited()

    def test_permission_error_403(self):
        client = _build_client()
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.remove_driver",
                new=AsyncMock(side_effect=PermissionError("Bot lacks permission to remove roles")),
            ),
        ):
            resp = client.delete("/api/drivers/111")
        assert resp.status_code == 403

    def test_bot_not_ready_503(self):
        client = _build_client()
        with patch(f"{MODULE}.get_bot", return_value=None):
            resp = client.delete("/api/drivers/111")
        assert resp.status_code == 503


class TestActorFallback:
    def test_missing_user_falls_back_to_unknown(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"
        client = TestClient(app)

        member = {"discord_user_id": "111", "discord_username": "alice", "display_name": "Alice"}
        with (
            patch(f"{MODULE}.get_bot", return_value=_fake_bot()),
            patch(
                f"{MODULE}.TempDriverService.remove_driver", new=AsyncMock(return_value=member)
            ) as mock_remove,
        ):
            resp = client.delete("/api/drivers/111")

        assert resp.status_code == 200
        mock_remove.assert_awaited_once_with("111", "unknown")
