"""Integration tests for /api/group-rides validation paths."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.routes.group_rides import router as group_rides_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(group_rides_router)
    return TestClient(app)


def test_group_rides_returns_503_when_bot_missing():
    """Without an initialized bot the endpoint should return 503."""
    client = _build_client()

    with patch("api.routes.group_rides.require_bot") as require_bot:
        require_bot.side_effect = HTTPException(status_code=503, detail="Bot not initialized")
        resp = client.post("/api/group-rides", json={"ride_type": "friday"})

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Bot not initialized"


def test_group_rides_rejects_invalid_ride_type():
    """Invalid ride_type values should yield 400 before reaching the LLM."""
    client = _build_client()
    fake_bot = MagicMock()
    fake_bot.is_ready.return_value = True

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        resp = client.post("/api/group-rides", json={"ride_type": "bogus"})

    assert resp.status_code == 400
    assert "ride_type" in resp.json()["detail"]


def test_group_rides_requires_message_id_when_ride_type_message_id():
    """ride_type=message_id without a message_id payload should 400."""
    client = _build_client()
    fake_bot = MagicMock()
    fake_bot.is_ready.return_value = True

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        resp = client.post("/api/group-rides", json={"ride_type": "message_id"})

    assert resp.status_code == 400
    assert "message_id" in resp.json()["detail"]
