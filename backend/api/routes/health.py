"""
Health Check Endpoint

Provides health check endpoints for monitoring bot, database, and service status.
"""

import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from shared.core.bot_instance import get_bot
from shared.core.database import AsyncSessionLocal
from shared.core.lifecycle import get_enabled_bot_names, get_failed_extensions

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint that verifies per-bot and database connectivity.

    Returns:
        JSONResponse with status 200 when healthy, 503 when degraded.
    """
    enabled_bot_names = get_enabled_bot_names()

    bots: dict[str, str] = {}
    all_bots_ok = True
    for name in sorted(enabled_bot_names):
        connected = get_bot(name) is not None
        bots[name.value] = "connected" if connected else "unavailable"
        if not connected:
            all_bots_ok = False

    failed_extensions_by_bot = {
        name.value: sorted(exts) for name, exts in get_failed_extensions().items() if exts
    }
    has_failed_extensions = bool(failed_extensions_by_bot)

    db_ok = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database unreachable")

    overall = "ok" if (db_ok and all_bots_ok and not has_failed_extensions) else "degraded"

    result: dict = {
        "status": overall,
        "database": "connected" if db_ok else "unavailable",
        "bots": bots,
    }
    if has_failed_extensions:
        result["failed_extensions"] = dict(sorted(failed_extensions_by_bot.items()))

    if overall == "degraded":
        return JSONResponse(status_code=503, content=result)
    return result


@router.get("/api/environment")
def get_environment():
    """
    Get the current environment.

    Returns:
        Dictionary with the current APP_ENV value.
    """
    app_env = os.getenv("APP_ENV", "local")
    logger.debug(app_env)
    return {"environment": app_env}
