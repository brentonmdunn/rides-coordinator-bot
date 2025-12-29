"""Ask Rides API Routes - Example Backend with Hardcoded Data."""

from fastapi import APIRouter

from api.dummy_data import ASK_RIDES_STATUS

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


@router.get("/status")
async def get_status():
    """
    Get status for all ask rides jobs.

    Returns hardcoded dummy data for portfolio demonstration.
    """
    return ASK_RIDES_STATUS
