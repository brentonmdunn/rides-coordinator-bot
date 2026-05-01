"""
Usernames API Endpoint

GET /api/usernames — returns all known Discord usernames for @mention autocomplete.
"""

import logging

from fastapi import APIRouter, HTTPException

from bot.services.locations_service import LocationsService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/usernames")
async def get_usernames():
    """Return all known Discord usernames for @mention autocomplete."""
    try:
        usernames = await LocationsService.get_all_discord_usernames()
        return {"usernames": usernames}
    except Exception:
        logger.exception("Failed to fetch usernames")
        raise HTTPException(status_code=500, detail="Failed to fetch usernames") from None
