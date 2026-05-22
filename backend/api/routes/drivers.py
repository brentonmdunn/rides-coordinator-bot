"""Driver role management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from bot.core.bot_instance import get_bot
from bot.services.driver_management_service import DriverManagementService
from bot.utils.constants import GUILD_ID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drivers", tags=["drivers"])


def _get_guild():
    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=503, detail="Guild not found")
    return guild


class AddDriverRequest(BaseModel):
    """Request model for adding the Driver role to a guild member."""

    discord_username: str


@router.get("")
async def list_drivers(request: Request):
    """List all guild members with the Driver role. Accessible to all authenticated users."""
    guild = _get_guild()
    drivers = DriverManagementService.get_drivers(guild)
    return {"drivers": drivers}


@router.get("/search", dependencies=[Depends(require_ride_coordinator)])
async def search_members(q: str, request: Request):
    """Search non-driver guild members by username for autocomplete."""
    if not q or len(q.strip()) < 2:
        return {"members": []}
    guild = _get_guild()
    members = DriverManagementService.search_non_drivers(q.strip(), guild)
    return {"members": members}


@router.post("", dependencies=[Depends(require_ride_coordinator)])
async def add_driver(body: AddDriverRequest, request: Request):
    """Add the Driver role to a guild member by username."""
    guild = _get_guild()
    try:
        member = await DriverManagementService.add_driver(body.discord_username.strip(), guild)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    user = getattr(request.state, "user", None) or {}
    logger.info(
        f"Driver role added to @{member['discord_username']} by {user.get('email', 'unknown')}"
    )
    return member


@router.delete("/{discord_user_id}", dependencies=[Depends(require_ride_coordinator)])
async def remove_driver(discord_user_id: str, request: Request):
    """Remove the Driver role from a guild member by Discord user ID."""
    guild = _get_guild()
    try:
        member = await DriverManagementService.remove_driver(discord_user_id, guild)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    user = getattr(request.state, "user", None) or {}
    logger.info(
        f"Driver role removed from @{member['discord_username']} by {user.get('email', 'unknown')}"
    )
    return {"ok": True}
