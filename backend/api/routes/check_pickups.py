"""Check Pickups API Routes."""

from fastapi import APIRouter, HTTPException

from bot.api import get_bot
from bot.core.enums import AskRidesMessage, ChannelIds
from bot.services.locations_service import LocationsService

router = APIRouter(prefix="/api/check-pickups", tags=["check-pickups"])

def get_pickup_status(discord_username: str):
    """
    Check if ride grouping has been sent out for this user.

    Returns:
        bool: True if ride grouping has been sent out, False otherwise
    """
    bot = get_bot()
    if not bot:
        return {"error": "Bot not initialized"}
    
    # TODO: Implement logic to check if ride grouping has been sent out for this user
    return False


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
                "message_found": False
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
        
        # Build user list with assignment status using the helper function
        users = []
        assigned_count = 0
        
        for user in usernames_reacted:
            # Use the helper function to check if user has a ride
            has_ride = get_pickup_status(str(user))
            if has_ride:
                assigned_count += 1
            
            users.append({
                "discord_username": str(user),
                "has_ride": has_ride
            })
        
        # Sort: unassigned first, then alphabetically
        users.sort(key=lambda x: (x["has_ride"], x["discord_username"]))
        
        return {
            "users": users,
            "total": len(users),
            "assigned": assigned_count,
            "message_found": True
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch ride coverage: {str(e)}"
        )
