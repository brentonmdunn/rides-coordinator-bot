"""Integration tests for /api/ask-rides/messages routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import require_ride_coordinator
from api.routes.ask_rides import router as ask_rides_router
from bot.core.enums import AskRidesMessageType
from bot.services.ask_rides_messages_service import EffectiveTemplate


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(ask_rides_router)
    app.dependency_overrides[require_ride_coordinator] = lambda: "coordinator@example.com"
    return TestClient(app)


def _all_defaults() -> dict[AskRidesMessageType, EffectiveTemplate]:
    from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

    return {
        message_type: EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        for message_type, template in DEFAULT_TEMPLATES.items()
    }


class TestGetMessageTemplates:
    def test_returns_all_four_defaults(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.AskRidesMessagesService.get_effective_templates",
            new=AsyncMock(return_value=_all_defaults()),
        ):
            resp = client.get("/api/ask-rides/messages")

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["templates"].keys()) == {t.value for t in AskRidesMessageType}
        assert body["templates"]["sunday_service"]["is_customized"] is False
        assert "default" in body["templates"]["sunday_service"]
        assert "allowed_colors" in body
        assert "ping" in body["allowed_placeholders"]["sunday_service"]
        assert "ping" not in body["allowed_placeholders"]["friday_fellowship"]


class TestUpdateMessageTemplate:
    def test_rejects_unknown_message_type(self):
        client = _build_client()
        resp = client.put(
            "/api/ask-rides/messages/not_a_type",
            json={"title": "t", "body": "b", "color": "teal"},
        )
        assert resp.status_code == 400

    def test_rejects_validation_error_as_422(self):
        client = _build_client()

        with patch(
            "api.routes.ask_rides.AskRidesMessagesService.update_template",
            new=AsyncMock(side_effect=ValueError("Title must not be empty")),
        ):
            resp = client.put(
                "/api/ask-rides/messages/friday_fellowship",
                json={"title": "", "body": "b", "color": "teal"},
            )

        assert resp.status_code == 422

    def test_saves_and_returns_updated_template(self):
        client = _build_client()
        updated = EffectiveTemplate(
            title="New title", body="New body {date}", color="teal", is_customized=True
        )

        with patch(
            "api.routes.ask_rides.AskRidesMessagesService.update_template",
            new=AsyncMock(return_value=updated),
        ) as mock_update:
            resp = client.put(
                "/api/ask-rides/messages/friday_fellowship",
                json={"title": "New title", "body": "New body {date}", "color": "teal"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "New title"
        assert body["is_customized"] is True
        mock_update.assert_awaited_once()
        args = mock_update.call_args.args
        assert args[0] == AskRidesMessageType.FRIDAY_FELLOWSHIP


class TestResetMessageTemplate:
    def test_rejects_unknown_message_type(self):
        client = _build_client()
        resp = client.delete("/api/ask-rides/messages/not_a_type")
        assert resp.status_code == 400

    def test_resets_to_default(self):
        client = _build_client()
        default = _all_defaults()[AskRidesMessageType.SUNDAY_CLASS]

        with (
            patch(
                "api.routes.ask_rides.AskRidesMessagesService.reset_template",
                new=AsyncMock(),
            ) as mock_reset,
            patch(
                "api.routes.ask_rides.AskRidesMessagesService.get_effective_template",
                new=AsyncMock(return_value=default),
            ),
        ):
            resp = client.delete("/api/ask-rides/messages/sunday_class")

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_customized"] is False
        mock_reset.assert_awaited_once_with(AskRidesMessageType.SUNDAY_CLASS)
