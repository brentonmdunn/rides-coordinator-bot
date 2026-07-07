"""API routes for the main rides coordinator global setting."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_ride_coordinator
from bot.core.bot_instance import get_bot
from bot.services.ride_coordinator_service import RideCoordinatorService, UserLookupStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


class SetCoordinatorRequest(BaseModel):
    """Request body for setting the main rides coordinator."""

    user_id: str = Field(description="Discord user ID of the main rides coordinator")


@router.get(
    "/coordinator",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Get Main Rides Coordinator",
    description="Returns the stored main rides coordinator user ID and, if the bot is "
    "ready, the resolved Discord username.",
)
async def get_coordinator() -> dict:
    """Return the stored coordinator ID plus resolved username when possible."""
    user_id = await RideCoordinatorService.get_coordinator_id()
    result: dict = {"user_id": user_id, "configured": user_id is not None}

    if user_id is None:
        return result

    bot = get_bot()
    if bot is not None and bot.is_ready():
        status, user = await RideCoordinatorService.try_resolve_discord_user(bot, user_id)
        if status == UserLookupStatus.VERIFIED and user is not None:
            result["username"] = user.name
            result["display_name"] = user.display_name
        elif status == UserLookupStatus.NOT_FOUND:
            result["warning"] = "No Discord user found with this ID"

    return result


@router.put(
    "/coordinator",
    dependencies=[Depends(require_ride_coordinator)],
    summary="Set Main Rides Coordinator",
    description="Sets the main rides coordinator user ID, with best-effort Discord verification.",
)
async def set_coordinator(request: SetCoordinatorRequest) -> dict:
    """Validate, optionally verify, and persist the coordinator user ID."""
    user_id = request.user_id

    if not RideCoordinatorService.is_valid_snowflake(user_id):
        raise HTTPException(
            status_code=422,
            detail="user_id must be a valid Discord snowflake (digits only, 17-20 characters)",
        )

    bot = get_bot()

    if bot is not None and bot.user is not None and str(bot.user.id) == user_id:
        raise HTTPException(
            status_code=422, detail="Cannot set the bot's own user ID as the rides coordinator"
        )

    warning: str | None = None
    username: str | None = None

    if bot is not None and bot.is_ready():
        status, user = await RideCoordinatorService.try_resolve_discord_user(bot, user_id)
        if status == UserLookupStatus.NOT_FOUND:
            raise HTTPException(status_code=422, detail="No Discord user found with this ID")
        if status == UserLookupStatus.VERIFIED and user is not None:
            username = user.name
        else:
            # UserLookupStatus.UNAVAILABLE — best-effort only, never blocks the save.
            warning = "Could not verify this ID right now"
    else:
        warning = "Could not verify this ID right now"

    try:
        await RideCoordinatorService.set_coordinator_id(user_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        logger.exception("Failed to save main rides coordinator")
        raise HTTPException(status_code=500, detail=f"Failed to save coordinator: {e!s}") from e

    result: dict = {"user_id": user_id, "configured": True}
    if username is not None:
        result["username"] = username
    if warning is not None:
        result["warning"] = warning
    return result
