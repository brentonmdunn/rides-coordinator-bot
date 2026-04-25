"""
Health Check Endpoint

Provides health check endpoints for monitoring bot, database, and service status.
"""

import logging
import os

from fastapi import APIRouter
from sqlalchemy import text

from bot.core.bot_instance import get_bot
from bot.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint that verifies bot and database connectivity.

    Returns:
        Status dictionary with overall health and component statuses.
    """
    bot = get_bot()
    bot_ok = bot is not None and bot.is_ready()

    db_ok = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database unreachable")

    overall = "ok" if (bot_ok and db_ok) else "degraded"

    return {
        "status": overall,
        "bot": "connected" if bot_ok else "unavailable",
        "database": "connected" if db_ok else "unavailable",
    }


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
