"""
Usernames API Endpoint

GET /api/usernames — returns Discord username + display name pairs for @mention autocomplete.
"""

import logging

from fastapi import APIRouter, HTTPException

from bot.services.locations_service import LocationsService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/usernames")
async def get_usernames():
    """Return Discord username + name pairs for @mention autocomplete."""
    try:
        pairs = await LocationsService.get_all_discord_usernames()
        return {"users": [{"username": u, "name": n} for u, n in pairs]}
    except Exception:
        logger.exception("Failed to fetch usernames")
        raise HTTPException(status_code=500, detail="Failed to fetch usernames") from None
