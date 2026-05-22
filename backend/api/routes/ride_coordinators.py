"""Ride Coordinator role management API endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from bot.core.bot_instance import get_bot
from bot.core.enums import RoleIds
from bot.services.role_management_service import RoleManagementService
from bot.utils.constants import GUILD_ID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ride-coordinators", tags=["ride-coordinators"])


def _get_guild():
    bot = get_bot()
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=503, detail="Guild not found")
    return guild


class AddRideCoordinatorRequest(BaseModel):
    """Request model for adding the Ride Coordinator role to a guild member."""

    discord_username: str


@router.get("")
async def list_ride_coordinators(request: Request):
    """List all guild members with the Ride Coordinator role. Accessible to all authenticated users."""
    guild = _get_guild()
    members = RoleManagementService.get_members(guild, RoleIds.RIDE_COORDINATOR)
    return {"members": members}


@router.get("/search", dependencies=[Depends(require_ride_coordinator)])
async def search_members(q: str, request: Request):
    """Search non-ride-coordinator guild members by username for autocomplete."""
    if not q or len(q.strip()) < 2:
        return {"members": []}
    guild = _get_guild()
    members = RoleManagementService.search_non_members(q.strip(), guild, RoleIds.RIDE_COORDINATOR)
    return {"members": members}


@router.post("", dependencies=[Depends(require_ride_coordinator)])
async def add_ride_coordinator(body: AddRideCoordinatorRequest, request: Request):
    """Add the Ride Coordinator role to a guild member by username."""
    guild = _get_guild()
    try:
        member = await RoleManagementService.add_member(
            body.discord_username.strip(), guild, RoleIds.RIDE_COORDINATOR
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    user = getattr(request.state, "user", None) or {}
    logger.info(
        "Ride Coordinator role added to @%s by %s",
        member["discord_username"],
        user.get("email", "unknown"),
    )
    return member


@router.delete("/{discord_user_id}", dependencies=[Depends(require_ride_coordinator)])
async def remove_ride_coordinator(discord_user_id: str, request: Request):
    """Remove the Ride Coordinator role from a guild member by Discord user ID."""
    guild = _get_guild()
    try:
        member = await RoleManagementService.remove_member(
            discord_user_id, guild, RoleIds.RIDE_COORDINATOR
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    user = getattr(request.state, "user", None) or {}
    logger.info(
        "Ride Coordinator role removed from @%s by %s",
        member["discord_username"],
        user.get("email", "unknown"),
    )
    return {"ok": True}
