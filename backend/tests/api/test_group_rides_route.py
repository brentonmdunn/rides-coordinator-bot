"""Integration tests for /api/group-rides covering validation and rate limits."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.rate_limit import limiter
from api.routes.group_rides import router as group_rides_router


def _build_app() -> FastAPI:
    """Assemble a FastAPI app with rate limiting wired the same as production."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(group_rides_router)
    return app


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset the slowapi in-memory store between tests so limits don't bleed."""
    limiter.reset()
    yield
    limiter.reset()


def test_group_rides_returns_503_when_bot_missing():
    """Without an initialized bot the endpoint should return 503."""
    app = _build_app()
    client = TestClient(app)

    with patch("api.routes.group_rides.require_bot") as require_bot:
        require_bot.side_effect = __import__("fastapi").HTTPException(
            status_code=503, detail="Bot not initialized"
        )
        resp = client.post("/api/group-rides", json={"ride_type": "friday"})

    assert resp.status_code == 503
    assert resp.json()["detail"] == "Bot not initialized"


def test_group_rides_rejects_invalid_ride_type(fake_bot):
    """Invalid ride_type values should yield 400 before reaching the LLM."""
    app = _build_app()
    client = TestClient(app)

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        resp = client.post("/api/group-rides", json={"ride_type": "bogus"})

    assert resp.status_code == 400
    assert "ride_type" in resp.json()["detail"]


def test_group_rides_requires_message_id_when_ride_type_message_id(fake_bot):
    """ride_type=message_id without a message_id payload should 400."""
    app = _build_app()
    client = TestClient(app)

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        resp = client.post("/api/group-rides", json={"ride_type": "message_id"})

    assert resp.status_code == 400
    assert "message_id" in resp.json()["detail"]


def test_group_rides_rate_limit_returns_429(fake_bot):
    """The endpoint is capped at 10 requests per minute per client IP."""
    app = _build_app()
    client = TestClient(app)

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        # 10 invalid-but-fast calls inside the limit, all return 400.
        for _ in range(10):
            resp = client.post("/api/group-rides", json={"ride_type": "bogus"})
            assert resp.status_code == 400
        # The 11th call within the same minute trips the limiter.
        resp = client.post("/api/group-rides", json={"ride_type": "bogus"})

    assert resp.status_code == 429
