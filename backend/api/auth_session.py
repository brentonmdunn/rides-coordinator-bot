"""
Self-hosted session cookie authentication.

Drop-in replacement for cloudflare_access_middleware. Reads a `rides_session`
httpOnly cookie, validates against the auth_sessions DB table, enforces CSRF
on state-changing requests, and attaches the user to request.state.user.

Selected via AUTH_PROVIDER=self in app.py.
"""

import logging
import os

from fastapi import Request, Response

from bot.core.database import AsyncSessionLocal
from bot.core.logger import generate_txn_id, txn_id_var, user_email_var
from bot.services.auth_service import AuthService

logger = logging.getLogger(__name__)

APP_ENV = os.getenv("APP_ENV", "local")
# Set LOCAL_USE_DISCORD_OAUTH=true to test real Discord OAuth flow in local dev.
# When false (default), all requests get the dev@example.com mock user.
LOCAL_USE_DISCORD_OAUTH = os.getenv("LOCAL_USE_DISCORD_OAUTH", "false").lower() == "true"
SESSION_COOKIE_NAME = "rides_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths that don't require a session (OAuth flow + health check).
_EXEMPT_PATHS = {
    "/health",
    "/api/auth/discord/login",
    "/api/auth/discord/callback",
    "/api/auth/logout",
}


async def session_cookie_middleware(request: Request, call_next) -> Response:
    """
    ASGI middleware matching the shape of cloudflare_access_middleware.

    Sets request.state.user = {"email": str} on success.
    Returns 401 for missing/expired sessions, 403 for CSRF failures.
    """
    if APP_ENV == "local" and not LOCAL_USE_DISCORD_OAUTH:
        request.state.user = {"email": "dev@example.com"}
        email_token = user_email_var.set("dev@example.com")
        txn_token = txn_id_var.set(generate_txn_id())
        try:
            return await call_next(request)
        finally:
            txn_id_var.reset(txn_token)
            user_email_var.reset(email_token)

    path = request.url.path

    # Let static files and SPA HTML pass through; JS handles the redirect to /login.
    if not path.startswith("/api/"):
        return await call_next(request)

    # Auth flow and health endpoints are exempt.
    if path in _EXEMPT_PATHS:
        return await call_next(request)

    session_id_plain = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id_plain:
        return Response("Unauthorized", status_code=401)

    async with AsyncSessionLocal() as db_session:
        auth_session = await AuthService.get_session(db_session, session_id_plain)
        if not auth_session:
            return Response("Unauthorized", status_code=401)

        # CSRF check for state-changing requests.
        if request.method not in SAFE_METHODS:
            csrf_header = request.headers.get(CSRF_HEADER)
            if not AuthService.verify_csrf(auth_session.csrf_token, csrf_header):
                logger.warning(f"CSRF check failed for {request.method} {path}")
                return Response("Forbidden", status_code=403)

        # Slide expiry (throttled inside touch_session).
        await AuthService.touch_session(db_session, session_id_plain, auth_session)

    email = auth_session.email
    request.state.user = {"email": email}
    email_token = user_email_var.set(email)
    txn_token = txn_id_var.set(generate_txn_id())
    try:
        return await call_next(request)
    finally:
        txn_id_var.reset(txn_token)
        user_email_var.reset(email_token)
