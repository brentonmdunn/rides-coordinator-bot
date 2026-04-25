"""Shared FastAPI dependencies for common validation and parameter parsing."""

from discord.ext.commands import Bot
from fastapi import HTTPException

from bot.core.bot_instance import get_bot
from bot.core.enums import JobName

VALID_RIDE_TYPES = frozenset({JobName.FRIDAY, JobName.SUNDAY, "message_id"})
VALID_RIDE_TYPES_NO_MSG = frozenset({JobName.FRIDAY, JobName.SUNDAY})


def require_bot() -> Bot:
    """Dependency that returns the bot instance or raises 503."""
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    return bot


def require_ready_bot() -> Bot:
    """Dependency that returns the bot instance only if it is ready."""
    bot = get_bot()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot not initialized or not ready")
    return bot


def validate_ride_type(ride_type: str, *, allow_message_id: bool = True) -> str:
    """
    Validate a ride_type string against allowed values.

    Args:
        ride_type: The ride type to validate.
        allow_message_id: Whether ``"message_id"`` is an accepted value.

    Returns:
        The validated ride_type string.

    Raises:
        HTTPException: If the value is not recognised.
    """
    allowed = VALID_RIDE_TYPES if allow_message_id else VALID_RIDE_TYPES_NO_MSG
    if ride_type not in allowed:
        detail = f"ride_type must be one of: {', '.join(sorted(allowed))}"
        raise HTTPException(status_code=400, detail=detail)
    return ride_type


def parse_int_param(value: str | None, name: str) -> int:
    """Parse a string parameter to int, raising HTTPException on failure."""
    if value is None:
        raise HTTPException(status_code=400, detail=f"{name} is required")
    try:
        return int(value)
    except (ValueError, TypeError):
        raise HTTPException(  # noqa: B904
            status_code=400, detail=f"{name} must be a valid integer"
        )
