"""Integration tests for the /health and /api/environment routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.health import router as health_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router)
    return TestClient(app)


def test_health_returns_degraded_when_bot_missing():
    """When no bot is registered the health endpoint reports degraded status."""
    client = _build_client()

    with (
        patch("api.routes.health.get_bot", return_value=None),
        patch("api.routes.health.AsyncSessionLocal") as session_factory,
    ):
        # Make the DB context manager raise so we exercise the failure path.
        session_factory.side_effect = RuntimeError("db unavailable")
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["bot"] == "unavailable"
    assert body["database"] == "unavailable"


def test_health_returns_ok_when_bot_and_db_ready():
    """Healthy bot + DB should produce status=ok."""
    client = _build_client()
    fake_bot = MagicMock()
    fake_bot.is_ready.return_value = True

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, _stmt):
            return None

    with (
        patch("api.routes.health.get_bot", return_value=fake_bot),
        patch("api.routes.health.AsyncSessionLocal", return_value=_FakeSession()),
    ):
        resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "bot": "connected", "database": "connected"}


def test_environment_endpoint_reports_app_env(monkeypatch):
    """/api/environment echoes the configured APP_ENV value."""
    monkeypatch.setenv("APP_ENV", "production")
    client = _build_client()

    resp = client.get("/api/environment")

    assert resp.status_code == 200
    assert resp.json() == {"environment": "production"}
