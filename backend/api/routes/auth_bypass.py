"""
Emergency bypass login route.

Provides password-based access when BYPASS_DISCORD=true.
Only mounted when AUTH_PROVIDER=self; returns 404 when feature is disabled.
"""

import logging
import os

import bcrypt
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.constants import BYPASS_SESSION_TTL, CSRF_COOKIE_NAME, SESSION_COOKIE_NAME
from bot.core.database import AsyncSessionLocal
from bot.repositories.user_accounts_repository import UserAccountsRepository
from bot.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

APP_ENV = os.getenv("APP_ENV", "local")
BYPASS_DISCORD = os.getenv("BYPASS_DISCORD", "").lower() == "true"
BYPASS_PASSWORD_HASH = os.getenv("BYPASS_PASSWORD", "")
BYPASS_EMAIL = os.getenv("BYPASS_EMAIL", "bypass-emergency@local")

SESSION_COOKIE = SESSION_COOKIE_NAME
CSRF_COOKIE = CSRF_COOKIE_NAME
_IS_PROD = APP_ENV != "local"
_COOKIE_TTL = BYPASS_SESSION_TTL  # 24 hours — shared credential, shorter TTL limits blast radius


class BypassLoginRequest(BaseModel):
    """Request body for emergency bypass login."""

    password: str


@router.post("/api/auth/bypass/login")
async def bypass_login(body: BypassLoginRequest) -> JSONResponse:
    """Verify the shared emergency password and issue a session cookie."""
    if not BYPASS_DISCORD:
        return JSONResponse({"detail": "Not found"}, status_code=404)

    if not BYPASS_PASSWORD_HASH:
        logger.error("BYPASS_DISCORD=true but BYPASS_PASSWORD is not set")
        return JSONResponse({"detail": "Server misconfigured"}, status_code=500)

    if not bcrypt.checkpw(body.password.encode(), BYPASS_PASSWORD_HASH.encode()):
        logger.warning("Bypass login attempt with incorrect password")
        return JSONResponse({"detail": "Invalid password"}, status_code=401)

    async with AsyncSessionLocal() as db_session:
        account = await UserAccountsRepository.get_by_email(db_session, BYPASS_EMAIL)
        if not account:
            logger.error(f"Bypass account '{BYPASS_EMAIL}' not found — was seeding skipped?")
            return JSONResponse({"detail": "Server misconfigured"}, status_code=500)

        if account.email is None:
            logger.error(f"Bypass account '{BYPASS_EMAIL}' has no email — was it seeded correctly?")
            return JSONResponse({"detail": "Server misconfigured"}, status_code=500)
        session_id_plain, csrf_token = await AuthService.create_session(db_session, account.email)

    response = JSONResponse({"ok": True})
    response.set_cookie(
        SESSION_COOKIE,
        session_id_plain,
        max_age=_COOKIE_TTL,
        httponly=True,
        samesite="lax",
        secure=_IS_PROD,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=_COOKIE_TTL,
        httponly=False,
        samesite="lax",
        secure=_IS_PROD,
    )
    logger.info(f"Bypass login successful for '{BYPASS_EMAIL}'")
    return response


@router.get("/api/auth/bypass/config")
async def bypass_config() -> JSONResponse:
    """Return whether emergency bypass login is available. Unauthenticated."""
    return JSONResponse({"bypass_enabled": BYPASS_DISCORD})
