"""Ask Rides API Routes."""

from fastapi import APIRouter

from bot.api import get_bot
from bot.jobs.ask_rides import get_ask_rides_status

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


@router.get("/status")
async def get_status():
    """
    Get status for all ask rides jobs.
    
    Returns:
        Dictionary with status for friday, sunday, and sunday_class jobs
    """
    bot = get_bot()
    if not bot:
        return {"error": "Bot not initialized"}
    
    status = await get_ask_rides_status(bot)
    return status
