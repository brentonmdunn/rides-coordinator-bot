"""Unit tests for session_cookie_middleware."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.auth_session import SESSION_COOKIE_NAME, session_cookie_middleware
from bot.core.models import AuthSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_auth_session(
    email: str = "user@example.com",
    csrf_token: str = "good-csrf",
    expired: bool = False,
) -> AuthSession:
    s = MagicMock(spec=AuthSession)
    s.email = email
    s.csrf_token = csrf_token
    s.expires_at = (
        datetime.utcnow() - timedelta(seconds=1)
        if expired
        else datetime.utcnow() + timedelta(days=30)
    )
    s.last_activity_at = datetime.utcnow()
    return s


def _make_app(env: str = "production") -> TestClient:
    """Build a minimal FastAPI app wrapped in session_cookie_middleware."""
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    @app.post("/api/data")
    async def data_post():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    with patch("api.auth_session.APP_ENV", env):
        return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Local bypass
# ---------------------------------------------------------------------------


def test_local_mode_bypasses_auth():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    with (
        patch("api.auth_session.APP_ENV", "local"),
        patch("api.auth_session.LOCAL_USE_DISCORD_OAUTH", False),
    ):
        client = TestClient(app)
        resp = client.get("/api/data")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Exempt paths
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/api/auth/discord/login",
        "/api/auth/discord/callback",
        "/api/auth/logout",
    ],
)
def test_exempt_paths_pass_through(path):
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get(path)
    @app.post(path)
    async def exempt():
        return {"ok": True}

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.LOCAL_USE_DISCORD_OAUTH", False),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(path)

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Non-API paths (SPA static files)
# ---------------------------------------------------------------------------


def test_non_api_path_passes_through():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/some-page")
    async def spa():
        return {"ok": True}

    with patch("api.auth_session.APP_ENV", "production"):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/some-page")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Missing cookie → 401
# ---------------------------------------------------------------------------


def test_missing_session_cookie_returns_401():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    with patch("api.auth_session.APP_ENV", "production"):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/data")

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Invalid / missing session in DB → 401
# ---------------------------------------------------------------------------


def test_invalid_session_returns_401():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.AsyncSessionLocal", return_value=mock_db),
        patch("api.auth_session.AuthService.get_session", new=AsyncMock(return_value=None)),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/data", cookies={SESSION_COOKIE_NAME: "bad-token"})

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Valid session → request proceeds
# ---------------------------------------------------------------------------


def test_valid_session_attaches_user_and_proceeds():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)
    captured = {}

    @app.get("/api/data")
    async def data(request: Request):
        captured["user"] = getattr(request.state, "user", None)
        return {"ok": True}

    auth_session = _make_auth_session(email="test@example.com")
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.AsyncSessionLocal", return_value=mock_db),
        patch("api.auth_session.AuthService.get_session", new=AsyncMock(return_value=auth_session)),
        patch("api.auth_session.AuthService.touch_session", new=AsyncMock()),
    ):
        client = TestClient(
            app, raise_server_exceptions=False, cookies={SESSION_COOKIE_NAME: "good-token"}
        )
        resp = client.get("/api/data")

    assert resp.status_code == 200
    assert captured["user"] == {"email": "test@example.com"}


# ---------------------------------------------------------------------------
# CSRF enforcement
# ---------------------------------------------------------------------------


def test_post_without_csrf_header_returns_403():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.post("/api/data")
    async def data():
        return {"ok": True}

    auth_session = _make_auth_session(csrf_token="correct-csrf")
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.AsyncSessionLocal", return_value=mock_db),
        patch("api.auth_session.AuthService.get_session", new=AsyncMock(return_value=auth_session)),
        patch("api.auth_session.AuthService.touch_session", new=AsyncMock()),
        patch(
            "api.auth_session.AuthService.verify_csrf",
            side_effect=lambda expected, provided: provided == expected,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/data", cookies={SESSION_COOKIE_NAME: "good-token"})

    assert resp.status_code == 403


def test_post_with_correct_csrf_header_succeeds():
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.post("/api/data")
    async def data():
        return {"ok": True}

    auth_session = _make_auth_session(csrf_token="correct-csrf")
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.AsyncSessionLocal", return_value=mock_db),
        patch("api.auth_session.AuthService.get_session", new=AsyncMock(return_value=auth_session)),
        patch("api.auth_session.AuthService.touch_session", new=AsyncMock()),
        patch(
            "api.auth_session.AuthService.verify_csrf",
            side_effect=lambda expected, provided: provided == expected,
        ),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/data",
            cookies={SESSION_COOKIE_NAME: "good-token"},
            headers={"X-CSRF-Token": "correct-csrf"},
        )

    assert resp.status_code == 200


def test_get_request_skips_csrf_check():
    """GET is a safe method — no CSRF header required."""
    app = FastAPI()
    app.middleware("http")(session_cookie_middleware)

    @app.get("/api/data")
    async def data():
        return {"ok": True}

    auth_session = _make_auth_session(csrf_token="correct-csrf")
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("api.auth_session.APP_ENV", "production"),
        patch("api.auth_session.AsyncSessionLocal", return_value=mock_db),
        patch("api.auth_session.AuthService.get_session", new=AsyncMock(return_value=auth_session)),
        patch("api.auth_session.AuthService.touch_session", new=AsyncMock()),
    ):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/data", cookies={SESSION_COOKIE_NAME: "good-token"})

    assert resp.status_code == 200
