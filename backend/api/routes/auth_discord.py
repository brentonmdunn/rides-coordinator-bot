"""
Discord OAuth2 authentication routes.

Handles the full OAuth flow: login redirect, callback, and logout.
Only mounted when AUTH_PROVIDER=self.
"""

import hmac
import logging
import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from bot.core.database import AsyncSessionLocal
from bot.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

APP_ENV = os.getenv("APP_ENV", "local")
DISCORD_CLIENT_ID = os.getenv("DISCORD_OAUTH_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_OAUTH_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_OAUTH_REDIRECT_URI")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

_DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
_DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
_DISCORD_USER_URL = "https://discord.com/api/users/@me"

SESSION_COOKIE = "rides_session"
CSRF_COOKIE = "csrf_token"
_IS_PROD = APP_ENV != "local"


def _login_error_redirect(code: str) -> RedirectResponse:
    return RedirectResponse(f"{FRONTEND_BASE_URL}/login?error={code}")


@router.get("/api/auth/discord/login")
async def discord_login() -> RedirectResponse:
    """Redirect the user to Discord's OAuth consent screen."""
    if not DISCORD_CLIENT_ID or not DISCORD_REDIRECT_URI:
        logger.error("DISCORD_OAUTH_CLIENT_ID or DISCORD_OAUTH_REDIRECT_URI not configured")
        return _login_error_redirect("server_misconfigured")

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email",
        "state": state,
    }
    discord_url = f"{_DISCORD_AUTH_URL}?{urlencode(params)}"
    response = RedirectResponse(discord_url)
    response.set_cookie(
        "oauth_state",
        state,
        max_age=600,
        httponly=True,
        samesite="lax",
        path="/api/auth/discord/callback",
        secure=_IS_PROD,
    )
    return response


@router.get("/api/auth/discord/callback")
async def discord_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """
    Handle Discord's redirect back after user authorization.

    Validates the state parameter, exchanges the code for a token, fetches
    the Discord user, runs the identity-matching cascade, and issues a session.
    """
    if error or not code or not state:
        return _login_error_redirect("access_denied")

    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or not hmac.compare_digest(state, cookie_state):
        logger.warning("OAuth state mismatch — possible CSRF on login flow")
        return _login_error_redirect("invalid_state")

    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET or not DISCORD_REDIRECT_URI:
        logger.error("Discord OAuth env vars not configured")
        return _login_error_redirect("server_misconfigured")

    try:
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(
                _DISCORD_TOKEN_URL,
                data={
                    "client_id": DISCORD_CLIENT_ID,
                    "client_secret": DISCORD_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": DISCORD_REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if not token_resp.is_success:
                logger.error(f"Discord token exchange failed: {token_resp.status_code}")
                return _login_error_redirect("token_exchange_failed")
            access_token = token_resp.json()["access_token"]

            user_resp = await client.get(
                _DISCORD_USER_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if not user_resp.is_success:
                logger.error(f"Discord user fetch failed: {user_resp.status_code}")
                return _login_error_redirect("user_fetch_failed")
            discord_user = user_resp.json()
    except Exception:
        logger.exception("Error during Discord OAuth exchange")
        return _login_error_redirect("oauth_error")

    if not discord_user.get("verified"):
        logger.warning(
            f"Login rejected: Discord email unverified for user {discord_user.get('id')}"
        )
        return _login_error_redirect("email_not_verified")

    discord_user_id: str = discord_user["id"]
    discord_username: str = discord_user["username"]
    email: str | None = discord_user.get("email")

    async with AsyncSessionLocal() as db_session:
        account = await AuthService.match_or_reject(
            db_session, discord_user_id, discord_username, email
        )
        if not account:
            logger.info(f"Login rejected: not invited (discord_username={discord_username})")
            return _login_error_redirect("not_invited")

        session_id_plain, csrf_token = await AuthService.create_session(db_session, account.email)

    response = RedirectResponse(FRONTEND_BASE_URL)
    response.delete_cookie("oauth_state", path="/api/auth/discord/callback")
    _cookie_ttl = 30 * 24 * 60 * 60  # 30 days in seconds
    response.set_cookie(
        SESSION_COOKIE,
        session_id_plain,
        max_age=_cookie_ttl,
        httponly=True,
        samesite="lax",
        secure=_IS_PROD,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=_cookie_ttl,
        httponly=False,
        samesite="lax",
        secure=_IS_PROD,
    )
    return response


@router.post("/api/auth/logout")
async def logout(request: Request) -> JSONResponse:
    """
    Revoke the current session server-side, then clear cookies.

    Safe to call even if the session is already expired or missing.
    """
    session_id_plain = request.cookies.get(SESSION_COOKIE)
    if session_id_plain:
        try:
            async with AsyncSessionLocal() as db_session:
                await AuthService.revoke_session(db_session, session_id_plain)
        except Exception:
            logger.exception("Error revoking session during logout")

    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    response.delete_cookie(CSRF_COOKIE)
    return response
