"""
User Preferences API Endpoint

GET  /api/me/preferences  — fetch current user's preferences (creates defaults on first call)
PATCH /api/me/preferences  — update one or more preference fields
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from bot.services.user_preferences_service import UserPreferencesService

router = APIRouter()


@router.get("/api/me/preferences")
async def get_preferences(request: Request):
    """Return the current user's preferences.

    Creates a default preferences row on the first call so callers always
    receive a valid object.

    Returns:
        JSON with all preference fields.
    """
    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")

    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    prefs = await UserPreferencesService.get_preferences(email)
    return {"show_map_labels": prefs.show_map_labels}


class UpdatePreferencesRequest(BaseModel):
    """Request body for PATCH /api/me/preferences.

    All fields are optional — only supplied fields are updated.
    """

    show_map_labels: bool | None = None


@router.patch("/api/me/preferences")
async def update_preferences(request: Request, body: UpdatePreferencesRequest):
    """Update one or more preference fields for the current user.

    Args:
        body: Preference fields to update (any subset).

    Returns:
        JSON with the full updated preferences.
    """
    user = getattr(request.state, "user", None) or {}
    email = user.get("email", "")

    if not email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Ensure the row exists before patching
    await UserPreferencesService.get_preferences(email)

    updated = None
    if body.show_map_labels is not None:
        updated = await UserPreferencesService.set_show_map_labels(email, body.show_map_labels)

    if updated is None:
        # No-op patch — just return current state
        prefs = await UserPreferencesService.get_preferences(email)
        return {"show_map_labels": prefs.show_map_labels}

    return {"show_map_labels": updated.show_map_labels}
