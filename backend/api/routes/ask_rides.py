"""Ask Rides API Routes."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException

from bot.api import get_bot
from bot.core.database import AsyncSessionLocal
from bot.core.enums import ChannelIds
from bot.core.logger import logger
from bot.jobs.ask_rides import get_ask_rides_status, run_ask_rides_all
from bot.repositories.locations_repository import LocationsRepository

router = APIRouter(prefix="/api/ask-rides", tags=["ask-rides"])


@router.post("/send-now")
async def send_now():
    """
    Manually trigger all ask rides messages immediately.

    This calls the same run_ask_rides_all function used by the scheduler,
    useful when the scheduled send was missed (e.g. due to a service crash).
    """
    bot = get_bot()
    if not bot or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot not initialized or not ready")

    try:
        await run_ask_rides_all(bot)
        return {"success": True, "message": "Ask rides messages sent successfully"}
    except Exception as e:
        logger.error(f"Error sending ask rides messages manually: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send messages: {e!s}") from e


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


@router.get("/reactions/{message_type}")
async def get_ask_rides_reactions(message_type: str):
    """
    Get detailed reaction breakdown for ask-rides messages.

    Args:
        message_type: One of "friday", "sunday", or "sunday_class"

    Returns:
        Dictionary with reactions mapping emojis to lists of usernames,
        username_to_name mapping, and message_found flag
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")

    # Validate message_type
    valid_types = ["friday", "sunday", "sunday_class"]
    if message_type.lower() not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"message_type must be one of: {', '.join(valid_types)}",
        )

    try:
        channel = bot.get_channel(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        if not channel:
            logger.error(f"Channel {ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS} not found")
            raise HTTPException(status_code=500, detail="Channel not found")

        # Search keywords for each message type
        keywords = {
            "friday": "friday",
            "sunday": "sunday service",
            "sunday_class": "theology class",
        }

        keyword = keywords.get(message_type.lower(), "")

        # Find the most recent message for this type
        # Search in the last 20 messages (same as get_last_message_reactions)
        target_message = None
        async for message in channel.history(limit=20):
            if message.embeds and keyword.lower() in message.embeds[0].description.lower():
                target_message = message
                break

        if not target_message:
            return {
                "message_type": message_type,
                "reactions": {},
                "username_to_name": {},
                "message_found": False,
            }

        # Collect reactions by emoji, excluding bot reactions
        reactions_by_emoji = defaultdict(list)
        all_usernames = set()

        for reaction in target_message.reactions:
            # Only process reactions that aren't from the bot itself
            emoji_str = str(reaction.emoji)
            async for user in reaction.users():
                if not user.bot:
                    username = user.name
                    reactions_by_emoji[emoji_str].append(username)
                    all_usernames.add(username)

        # Get display names for all usernames
        locations_repo = LocationsRepository()
        async with AsyncSessionLocal() as session:
            username_to_name = await locations_repo.get_names_for_usernames(session, all_usernames)

        return {
            "message_type": message_type,
            "reactions": dict(reactions_by_emoji),
            "username_to_name": username_to_name,
            "message_found": True,
        }

    except Exception as e:
        logger.error(f"Error fetching ask-rides reactions for {message_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
