"""Integration tests for the /health and /api/environment routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.health import router as health_router
from shared.core.enums import BotName


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router)
    return TestClient(app)


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _stmt):
        return None


def test_health_returns_ok_when_bot_and_db_ready():
    """Healthy bot + DB should produce status=ok with HTTP 200."""
    client = _build_client()
    fake_bot = MagicMock()

    with (
        patch("api.routes.health.get_enabled_bot_names", return_value={BotName.RIDEBOT}),
        patch("api.routes.health.get_bot", return_value=fake_bot),
        patch("api.routes.health.get_failed_extensions", return_value={}),
        patch("api.routes.health.AsyncSessionLocal", return_value=_FakeSession()),
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "database": "connected",
        "bots": {"ridebot": "connected"},
    }


def test_health_returns_degraded_when_bot_unavailable():
    """A registered but unavailable bot should mark the response degraded (503)."""
    client = _build_client()

    with (
        patch("api.routes.health.get_enabled_bot_names", return_value={BotName.RIDEBOT}),
        patch("api.routes.health.get_bot", return_value=None),
        patch("api.routes.health.get_failed_extensions", return_value={}),
        patch("api.routes.health.AsyncSessionLocal", return_value=_FakeSession()),
    ):
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "connected"
    assert body["bots"] == {"ridebot": "unavailable"}
    assert "failed_extensions" not in body


def test_health_returns_degraded_when_extensions_failed():
    """Failed extensions should mark the response degraded even if bots are up."""
    client = _build_client()
    fake_bot = MagicMock()

    with (
        patch("api.routes.health.get_enabled_bot_names", return_value={BotName.RIDEBOT}),
        patch("api.routes.health.get_bot", return_value=fake_bot),
        patch(
            "api.routes.health.get_failed_extensions",
            return_value={BotName.RIDEBOT: {"ridebot.cogs.b", "ridebot.cogs.a"}},
        ),
        patch("api.routes.health.AsyncSessionLocal", return_value=_FakeSession()),
    ):
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["bots"] == {"ridebot": "connected"}
    assert body["failed_extensions"] == {"ridebot": ["ridebot.cogs.a", "ridebot.cogs.b"]}


def test_health_returns_degraded_when_db_unavailable():
    """DB connectivity failures should mark the response degraded (503)."""
    client = _build_client()
    fake_bot = MagicMock()

    with (
        patch("api.routes.health.get_enabled_bot_names", return_value={BotName.RIDEBOT}),
        patch("api.routes.health.get_bot", return_value=fake_bot),
        patch("api.routes.health.get_failed_extensions", return_value={}),
        patch("api.routes.health.AsyncSessionLocal") as session_factory,
    ):
        session_factory.side_effect = RuntimeError("db unavailable")
        resp = client.get("/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["database"] == "unavailable"
    assert body["bots"] == {"ridebot": "connected"}


def test_health_ok_with_no_enabled_bots_and_db_ok():
    """API-only mode (no enabled bots) should depend only on the DB."""
    client = _build_client()

    with (
        patch("api.routes.health.get_enabled_bot_names", return_value=set()),
        patch("api.routes.health.get_failed_extensions", return_value={}),
        patch("api.routes.health.AsyncSessionLocal", return_value=_FakeSession()),
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "database": "connected",
        "bots": {},
    }


def test_environment_endpoint_reports_app_env(monkeypatch):
    """/api/environment echoes the configured APP_ENV value."""
    monkeypatch.setenv("APP_ENV", "production")
    client = _build_client()

    resp = client.get("/api/environment")

    assert resp.status_code == 200
    assert resp.json() == {"environment": "production"}
