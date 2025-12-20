"""
Example API Endpoints

Demonstrates API functionality and Discord bot integration.
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Request

from bot.api import get_bot

logger = logging.getLogger(__name__)
router = APIRouter()

DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "916823070017204274"))


@router.get("/api/hello")
def hello():
    """
    Simple hello endpoint.
    
    Returns:
        Greeting message.
    """
    return {"message": "Hello from the backend!"}


@router.post("/api/discord/send-message")
async def send_discord_message(request: Request):
    """
    Send a personalized message to the configured Discord channel.
    
    Args:
        request: FastAPI request containing user info
        
    Returns:
        JSON response with status
        
    Raises:
        HTTPException: If bot not ready or channel not found
    """
    bot = get_bot()
    
    if bot is None or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Discord bot not ready")
    
    # Get user email from request state
    user_email = request.state.user.get("email", "unknown user")
    message = f"Hello world from {user_email}"
    
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        raise HTTPException(
            status_code=404, 
            detail=f"Channel {DISCORD_CHANNEL_ID} not found or bot doesn't have access"
        )
    
    try:
        await channel.send(message)
        return {
            "status": "success",
            "message": "Message sent to Discord",
            "channel_id": DISCORD_CHANNEL_ID,
            "user_email": user_email
        }
    except Exception as e:
        logger.error(f"Failed to send Discord message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")
