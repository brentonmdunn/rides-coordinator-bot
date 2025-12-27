"""Check Pickups API Routes."""

from fastapi import APIRouter, HTTPException

from bot.api import get_bot
from bot.core.enums import AskRidesMessage, ChannelIds
from bot.core.logger import logger
from bot.services.locations_service import LocationsService
from bot.repositories.ride_coverage_repository import RideCoverageRepository
from bot.utils.time_helpers import get_last_sunday

router = APIRouter(prefix="/api/check-pickups", tags=["check-pickups"])


@router.get("/{ride_type}")
async def get_pickup_coverage(ride_type: str):
    """
    Check ride coverage for users who reacted to a ride message.
    
    Args:
        ride_type: Either "friday" or "sunday"
    
    Returns:
        Dictionary containing:
        - users: List of {discord_username: str, has_ride: bool}
        - total: Total number of users who reacted
        - assigned: Number of users with ride assignments
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    # Validate ride_type
    if ride_type.lower() not in ["friday", "sunday"]:
        raise HTTPException(
            status_code=400, 
            detail="ride_type must be 'friday' or 'sunday'"
        )
    
    try:
        locations_service = LocationsService(bot)
        ride_coverage_repo = RideCoverageRepository()
        
        # Determine which message to check based on ride type
        if ride_type.lower() == "friday":
            ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
        else:  # sunday
            ask_message = AskRidesMessage.SUNDAY_SERVICE
        
        # Find the most recent message for this ride type
        message_id = await locations_service._find_correct_message(
            ask_message, 
            int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        )
        
        if message_id is None:
            # No message found for this ride type yet
            return {
                "users": [],
                "total": 0,
                "assigned": 0,
                "message_found": False,
                "has_coverage_entries": False
            }
        
        # Get all users who reacted to the message
        usernames_reacted = await locations_service._get_usernames_who_reacted(
            int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS),
            message_id
        )
        
        # For Sunday, exclude users going to class
        if ride_type.lower() == "sunday":
            class_message_id = await locations_service._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS,
                int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )
            if class_message_id:
                class_usernames = await locations_service._get_usernames_who_reacted(
                    int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS),
                    class_message_id
                )
                usernames_reacted -= class_usernames
        
        # Build user list with assignment status using the repository
        # Use bulk check for performance
        usernames_list = [str(u) for u in usernames_reacted]
        covered_usernames = await ride_coverage_repo.get_bulk_coverage_status(usernames_list)
        
        users = []
        assigned_count = 0
        
        for username in usernames_list:
            has_ride = username in covered_usernames
            if has_ride:
                assigned_count += 1
            
            users.append({
                "discord_username": username,
                "has_ride": has_ride
            })
        
        # Sort: unassigned first, then alphabetically
        users.sort(key=lambda x: (x["has_ride"], x["discord_username"]))
        
        # Check if any coverage entries exist for the current week
        last_sunday = get_last_sunday()
        has_entries = await ride_coverage_repo.has_coverage_entries(last_sunday)
        
        return {
            "users": users,
            "total": len(users),
            "assigned": assigned_count,
            "message_found": True,
            "has_coverage_entries": has_entries
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ride coverage: {str(e)}"
        )


@router.post("/sync")
async def sync_ride_coverage():
    """
    Force sync ride coverage by scanning recent messages.
    
    Returns:
        Dictionary with sync results.
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get the RideCoverage cog
        ride_coverage_cog = bot.get_cog("RideCoverage")
        if not ride_coverage_cog:
            raise HTTPException(status_code=503, detail="RideCoverage cog not loaded")
        
        logger.info("API: Force sync ride coverage requested")
        result = await ride_coverage_cog.sync_ride_coverage()
        logger.info(f"API: Force sync completed: {result}")
        
        return {
            "success": True,
            "message": "Ride coverage sync completed",
            **result
        }
        
    except Exception as e:
        logger.error(f"API: Failed to sync ride coverage: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync ride coverage: {str(e)}"
        )
