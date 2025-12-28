"""
Health Check Endpoint

Provides a simple health check endpoint for monitoring.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns:
        Status dictionary indicating service is running.
    """
    return {"status": "ok"}
