"""
User Info API Endpoint

Returns the current authenticated user's information.
"""

import os

from fastapi import APIRouter, Request

from api.constants import ADMIN_EMAILS

router = APIRouter()

APP_ENV = os.getenv("APP_ENV", "local")


@router.get("/api/me")
async def get_current_user(request: Request):
    """
    Return the current authenticated user's email and admin status.

    Returns:
        JSON with user email and is_admin flag
    """
    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")
    allowed = ADMIN_EMAILS | ({"dev@example.com"} if APP_ENV == "local" else set())
    return {"email": email, "is_admin": email in allowed}
