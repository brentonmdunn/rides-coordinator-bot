"""Health Check API Route - Example Backend."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
def health():
    """Simple health check endpoint."""
    return {"status": "healthy", "mode": "example"}
