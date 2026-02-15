"""
User Info API Endpoint

Returns the current authenticated user's information.
"""

import os

from fastapi import APIRouter, Request

from api.constants import ADMIN_EMAIL

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
    allowed = [ADMIN_EMAIL]
    if APP_ENV == "local":
        allowed.append("dev@example.com")
    return {"email": email, "is_admin": email in allowed}
