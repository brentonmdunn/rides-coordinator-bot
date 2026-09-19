"""Driver role management API endpoints."""

import logging

import discord
from discord.ext.commands import Bot
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from ridebot.services.role_management_service import RoleManagementService
from ridebot.services.temp_driver_service import TempDriverService
from ridebot.utils.constants import GUILD_ID
from shared.core.bot_instance import get_bot
from shared.core.enums import BotName, RoleIds

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drivers", tags=["drivers"])


def _get_bot_and_guild() -> tuple[Bot, discord.Guild]:
    bot = get_bot(BotName.RIDEBOT)
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot is not ready")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=503, detail="Guild not found")
    return bot, guild


def _get_guild() -> discord.Guild:
    return _get_bot_and_guild()[1]


def _get_temp_driver_service() -> TempDriverService:
    """
    Build a TempDriverService for a ready bot and guild (503 otherwise).

    Ruling out guild unavailability here lets every ValueError from the service map to 400.
    """
    return TempDriverService(_get_bot_and_guild()[0])


def _get_actor(request: Request) -> str:
    user = getattr(request.state, "user", None) or {}
    return user.get("email", "unknown")


class AddDriverRequest(BaseModel):
    """Request model for adding the Driver role to a guild member."""

    discord_username: str


class AddTempDriverRequest(BaseModel):
    """Request model for granting a temporary Driver role."""

    discord_username: str
    duration: str | None = None


@router.get("")
async def list_drivers(request: Request):
    """List all guild members with the Driver role. Accessible to all authenticated users."""
    guild = _get_guild()
    members = RoleManagementService.get_members(guild, RoleIds.DRIVER)
    expiry_map = await TempDriverService.get_expiry_map()
    for member in members:
        expires_at = expiry_map.get(member["discord_user_id"])
        member["temp_expires_at"] = expires_at.isoformat() if expires_at else None
    return {"members": members}


@router.get("/search", dependencies=[Depends(require_ride_coordinator)])
async def search_members(q: str, request: Request):
    """Search non-driver guild members by username for autocomplete."""
    if not q or len(q.strip()) < 2:
        return {"members": []}
    guild = _get_guild()
    members = RoleManagementService.search_non_members(q.strip(), guild, RoleIds.DRIVER)
    return {"members": members}


@router.post("", dependencies=[Depends(require_ride_coordinator)])
async def add_driver(body: AddDriverRequest, request: Request):
    """Add the Driver role to a guild member permanently, converting any temp grant."""
    service = _get_temp_driver_service()
    try:
        member = await service.add_permanent_driver(body.discord_username.strip())
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    actor = _get_actor(request)
    logger.info("Driver role added to @%s by %s", member["discord_username"], actor)
    return member


@router.post("/temp", dependencies=[Depends(require_ride_coordinator)])
async def add_temp_driver(body: AddTempDriverRequest, request: Request):
    """Grant (or extend) a temporary Driver role for a guild member."""
    service = _get_temp_driver_service()
    actor = _get_actor(request)
    try:
        member = service.resolve_member(body.discord_username.strip())
        result = await service.grant(member, body.duration, actor, announce=True)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    logger.info(
        "Temporary driver role %s for @%s by %s (expires %s)",
        result.event,
        result.grant.discord_username,
        actor,
        result.grant.expires_at.isoformat(),
    )
    return {
        "discord_user_id": result.grant.discord_user_id,
        "discord_username": result.grant.discord_username,
        "display_name": result.grant.display_name,
        "expires_at": result.grant.expires_at.isoformat(),
        "previous_expires_at": (
            result.previous_expires_at.isoformat() if result.previous_expires_at else None
        ),
        "event": result.event,
    }


@router.delete("/{discord_user_id}", dependencies=[Depends(require_ride_coordinator)])
async def remove_driver(discord_user_id: str, request: Request):
    """Remove the Driver role from a guild member by Discord user ID."""
    service = _get_temp_driver_service()
    actor = _get_actor(request)
    try:
        member = await service.remove_driver(discord_user_id, actor)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))  # noqa: B904
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # noqa: B904

    logger.info(
        "Driver role removed from @%s by %s",
        member["discord_username"],
        actor,
    )
    return {"ok": True}
