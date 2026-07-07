"""Integration tests for /api/ask-rides/schedule routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.ask_rides import router as ask_rides_router
from bot.core.enums import AskRidesScheduleSlot
from bot.services.ask_rides_schedule_service import EffectiveSchedule


def _build_client(*, forbidden: bool = False) -> TestClient:
    app = FastAPI()
    app.include_router(ask_rides_router)

    if forbidden:

        def _raise_forbidden():
            raise HTTPException(status_code=403, detail="Forbidden")

        app.dependency_overrides[require_ride_coordinator] = _raise_forbidden
    else:
        app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"

    return TestClient(app)


def _default_schedules() -> dict[AskRidesScheduleSlot, EffectiveSchedule]:
    return {
        AskRidesScheduleSlot.WEDNESDAY_REMINDER: EffectiveSchedule(
            day_of_week=0, hour=11, minute=0, is_customized=False
        ),
        AskRidesScheduleSlot.FRI_SUN_GROUP: EffectiveSchedule(
            day_of_week=2, hour=12, minute=0, is_customized=False
        ),
    }


class TestGetSchedule:
    def test_returns_both_slots_with_allowed_days_and_time_window(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.get_effective_schedules",
            new=AsyncMock(return_value=_default_schedules()),
        ):
            resp = client.get("/api/ask-rides/schedule")

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["schedules"].keys()) == {s.value for s in AskRidesScheduleSlot}

        wed = body["schedules"]["wednesday_reminder"]
        assert wed["day_of_week"] == 0
        assert wed["hour"] == 11
        assert wed["minute"] == 0
        assert wed["is_customized"] is False
        assert wed["allowed_days"] == [0, 1]

        fri_sun = body["schedules"]["fri_sun_group"]
        assert fri_sun["allowed_days"] == [0, 1, 2, 3]

        assert body["time_window"] == {
            "min_hour": 6,
            "min_minute": 0,
            "max_hour": 22,
            "max_minute": 0,
        }

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.get("/api/ask-rides/schedule")
        assert resp.status_code == 403


class TestUpdateSchedule:
    def test_rejects_unknown_slot(self):
        client = _build_client()
        resp = client.put(
            "/api/ask-rides/schedule/not_a_slot",
            json={"day_of_week": 0, "hour": 11, "minute": 0},
        )
        assert resp.status_code == 400

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.put(
            "/api/ask-rides/schedule/wednesday_reminder",
            json={"day_of_week": 0, "hour": 11, "minute": 0},
        )
        assert resp.status_code == 403

    def test_rejects_validation_error_as_422(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.update_schedule",
            new=AsyncMock(side_effect=ValueError("day_of_week must be one of [0, 1]")),
        ):
            resp = client.put(
                "/api/ask-rides/schedule/wednesday_reminder",
                json={"day_of_week": 4, "hour": 11, "minute": 0},
            )

        assert resp.status_code == 422

    def test_saves_and_returns_updated_schedule(self):
        client = _build_client()
        updated = EffectiveSchedule(day_of_week=1, hour=9, minute=30, is_customized=True)

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.update_schedule",
            new=AsyncMock(return_value=(updated, True)),
        ) as mock_update:
            resp = client.put(
                "/api/ask-rides/schedule/wednesday_reminder",
                json={"day_of_week": 1, "hour": 9, "minute": 30},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["day_of_week"] == 1
        assert body["hour"] == 9
        assert body["minute"] == 30
        assert body["is_customized"] is True
        assert body["allowed_days"] == [0, 1]
        assert body["warning"] is None
        mock_update.assert_awaited_once()
        args = mock_update.call_args.args
        assert args[0] == AskRidesScheduleSlot.WEDNESDAY_REMINDER
        assert args[1:4] == (1, 9, 30)

    def test_warning_present_when_reschedule_not_applied_live(self):
        client = _build_client()
        updated = EffectiveSchedule(day_of_week=1, hour=9, minute=30, is_customized=True)

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.update_schedule",
            new=AsyncMock(return_value=(updated, False)),
        ):
            resp = client.put(
                "/api/ask-rides/schedule/wednesday_reminder",
                json={"day_of_week": 1, "hour": 9, "minute": 30},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["warning"] is not None
        assert "bot reconnects" in body["warning"]


class TestResetSchedule:
    def test_rejects_unknown_slot(self):
        client = _build_client()
        resp = client.delete("/api/ask-rides/schedule/not_a_slot")
        assert resp.status_code == 400

    def test_forbidden_for_viewer_role(self):
        client = _build_client(forbidden=True)
        resp = client.delete("/api/ask-rides/schedule/wednesday_reminder")
        assert resp.status_code == 403

    def test_resets_to_default(self):
        client = _build_client()
        default = EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=False)

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.reset_schedule",
            new=AsyncMock(return_value=(default, True)),
        ) as mock_reset:
            resp = client.delete("/api/ask-rides/schedule/wednesday_reminder")

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_customized"] is False
        assert body["warning"] is None
        mock_reset.assert_awaited_once_with(AskRidesScheduleSlot.WEDNESDAY_REMINDER)

    def test_warning_present_when_reschedule_not_applied_live(self):
        client = _build_client()
        default = EffectiveSchedule(day_of_week=0, hour=11, minute=0, is_customized=False)

        with patch(
            "api.routes.ask_rides.AskRidesScheduleService.reset_schedule",
            new=AsyncMock(return_value=(default, False)),
        ):
            resp = client.delete("/api/ask-rides/schedule/wednesday_reminder")

        assert resp.status_code == 200
        body = resp.json()
        assert body["warning"] is not None
