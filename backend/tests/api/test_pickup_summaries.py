"""Integration tests for /api/ask-rides/pickup-summaries routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.ask_rides import router as ask_rides_router
from ridebot.services.pickup_summary_service import EffectivePickupSummarySetting
from shared.core.enums import PickupSummarySlot


def _build_client(*, forbidden: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(ask_rides_router)

    @app.middleware("http")
    async def _inject_user(request, call_next):
        request.state.user = {"email": "coordinator@example.com"}
        return await call_next(request)

    if forbidden:

        def _raise_forbidden():
            raise HTTPException(status_code=403, detail="Forbidden")

        app.dependency_overrides[require_ride_coordinator] = _raise_forbidden
    else:
        app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"

    return TestClient(app)


def _default_settings() -> dict[PickupSummarySlot, EffectivePickupSummarySetting]:
    return {
        PickupSummarySlot.FRIDAY: EffectivePickupSummarySetting(
            enabled=True, day_of_week=4, hour=11, minute=0, is_customized=False
        ),
        PickupSummarySlot.SUNDAY: EffectivePickupSummarySetting(
            enabled=True, day_of_week=5, hour=16, minute=0, is_customized=False
        ),
    }


class TestGetPickupSummaries:
    def test_returns_both_slots_with_allowed_days_and_time_window(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.PickupSummaryService.get_effective_settings",
            new=AsyncMock(return_value=_default_settings()),
        ):
            resp = client.get("/api/ask-rides/pickup-summaries")

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["summaries"].keys()) == {s.value for s in PickupSummarySlot}

        friday = body["summaries"]["friday"]
        assert friday["enabled"] is True
        assert friday["day_of_week"] == 4
        assert friday["hour"] == 11
        assert friday["minute"] == 0
        assert friday["is_customized"] is False
        assert friday["allowed_days"] == [0, 1, 2, 3, 4]
        assert friday["default"] == {"day_of_week": 4, "hour": 11, "minute": 0}

        sunday = body["summaries"]["sunday"]
        assert sunday["allowed_days"] == [0, 1, 2, 3, 4, 5]
        assert sunday["default"] == {"day_of_week": 5, "hour": 16, "minute": 0}

        assert body["time_window"] == {
            "min_hour": 6,
            "min_minute": 0,
            "max_hour": 22,
            "max_minute": 0,
        }

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.get("/api/ask-rides/pickup-summaries")
        assert resp.status_code == 403


class TestUpdatePickupSummary:
    def test_rejects_unknown_slot(self):
        client = _build_client()
        resp = client.put(
            "/api/ask-rides/pickup-summaries/not_a_slot",
            json={"enabled": True, "day_of_week": 0, "hour": 11, "minute": 0},
        )
        assert resp.status_code == 400

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.put(
            "/api/ask-rides/pickup-summaries/friday",
            json={"enabled": True, "day_of_week": 0, "hour": 11, "minute": 0},
        )
        assert resp.status_code == 403

    def test_rejects_validation_error_as_422(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.PickupSummaryService.update_setting",
            new=AsyncMock(side_effect=ValueError("day_of_week must be one of [0, 1, 2, 3, 4]")),
        ):
            resp = client.put(
                "/api/ask-rides/pickup-summaries/friday",
                json={"enabled": True, "day_of_week": 6, "hour": 11, "minute": 0},
            )

        assert resp.status_code == 422

    def test_saves_and_returns_updated_setting(self):
        client = _build_client()
        updated = EffectivePickupSummarySetting(
            enabled=False, day_of_week=1, hour=9, minute=30, is_customized=True
        )

        with patch(
            "api.routes.ask_rides.PickupSummaryService.update_setting",
            new=AsyncMock(return_value=(updated, True)),
        ) as mock_update:
            resp = client.put(
                "/api/ask-rides/pickup-summaries/friday",
                json={"enabled": False, "day_of_week": 1, "hour": 9, "minute": 30},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled"] is False
        assert body["day_of_week"] == 1
        assert body["hour"] == 9
        assert body["minute"] == 30
        assert body["is_customized"] is True
        assert body["allowed_days"] == [0, 1, 2, 3, 4]
        assert body["warning"] is None
        mock_update.assert_awaited_once()
        args = mock_update.call_args.args
        assert args[0] == PickupSummarySlot.FRIDAY
        assert args[1:5] == (False, 1, 9, 30)

    def test_updated_by_taken_from_request_user(self):
        client = _build_client()
        updated = EffectivePickupSummarySetting(
            enabled=True, day_of_week=1, hour=9, minute=30, is_customized=True
        )

        with patch(
            "api.routes.ask_rides.PickupSummaryService.update_setting",
            new=AsyncMock(return_value=(updated, True)),
        ) as mock_update:
            client.put(
                "/api/ask-rides/pickup-summaries/friday",
                json={"enabled": True, "day_of_week": 1, "hour": 9, "minute": 30},
            )

        mock_update.assert_awaited_once()
        args = mock_update.call_args.args
        assert args[5] == "coordinator@example.com"

    def test_warning_present_when_reschedule_not_applied_live(self):
        client = _build_client()
        updated = EffectivePickupSummarySetting(
            enabled=True, day_of_week=1, hour=9, minute=30, is_customized=True
        )

        with patch(
            "api.routes.ask_rides.PickupSummaryService.update_setting",
            new=AsyncMock(return_value=(updated, False)),
        ):
            resp = client.put(
                "/api/ask-rides/pickup-summaries/friday",
                json={"enabled": True, "day_of_week": 1, "hour": 9, "minute": 30},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["warning"] is not None
        assert "bot reconnects" in body["warning"]


class TestResetPickupSummary:
    def test_rejects_unknown_slot(self):
        client = _build_client()
        resp = client.delete("/api/ask-rides/pickup-summaries/not_a_slot")
        assert resp.status_code == 400

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.delete("/api/ask-rides/pickup-summaries/friday")
        assert resp.status_code == 403

    def test_resets_to_default(self):
        client = _build_client()
        default = EffectivePickupSummarySetting(
            enabled=True, day_of_week=4, hour=11, minute=0, is_customized=False
        )

        with patch(
            "api.routes.ask_rides.PickupSummaryService.reset_setting",
            new=AsyncMock(return_value=(default, True)),
        ) as mock_reset:
            resp = client.delete("/api/ask-rides/pickup-summaries/friday")

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_customized"] is False
        assert body["warning"] is None
        mock_reset.assert_awaited_once_with(PickupSummarySlot.FRIDAY)

    def test_warning_present_when_reschedule_not_applied_live(self):
        client = _build_client()
        default = EffectivePickupSummarySetting(
            enabled=True, day_of_week=4, hour=11, minute=0, is_customized=False
        )

        with patch(
            "api.routes.ask_rides.PickupSummaryService.reset_setting",
            new=AsyncMock(return_value=(default, False)),
        ):
            resp = client.delete("/api/ask-rides/pickup-summaries/friday")

        assert resp.status_code == 200
        body = resp.json()
        assert body["warning"] is not None
