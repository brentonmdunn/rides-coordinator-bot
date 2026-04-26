"""Tests covering /api/group-rides rate limiting via slowapi."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
def _reset_limiter():
    """Reset the slowapi in-memory store between tests so limits don't bleed."""
    limiter.reset()
    yield
    limiter.reset()


def test_group_rides_rate_limit_returns_429():
    """The endpoint is capped at 10 requests per minute per client IP."""
    app = _build_app()
    client = TestClient(app)
    fake_bot = MagicMock()
    fake_bot.is_ready.return_value = True

    with patch("api.routes.group_rides.require_bot", return_value=fake_bot):
        # 10 invalid-but-fast calls inside the limit, all return 400.
        for _ in range(10):
            resp = client.post("/api/group-rides", json={"ride_type": "bogus"})
            assert resp.status_code == 400
        # The 11th call within the same minute trips the limiter.
        resp = client.post("/api/group-rides", json={"ride_type": "bogus"})

    assert resp.status_code == 429
