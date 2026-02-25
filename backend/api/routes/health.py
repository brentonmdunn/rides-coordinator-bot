"""
Health Check Endpoint

Provides a simple health check endpoint for monitoring.
"""

import os

from fastapi import APIRouter

from bot.core.logger import logger

router = APIRouter()


@router.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        Status dictionary indicating service is running.
    """
    return {"status": "ok"}


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
