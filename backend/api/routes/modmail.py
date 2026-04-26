"""
Modmail API Endpoints

Provides REST and WebSocket endpoints for the modmail web UI.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from api.auth import require_ride_coordinator
from api.dependencies import require_ready_bot
from bot.core.database import AsyncSessionLocal
from bot.repositories.modmail_messages_repository import ModmailMessagesRepository
from bot.repositories.modmail_repository import ModmailRepository
from bot.services.modmail_service import (
    ModmailAmbiguousUserError,
    ModmailConfigError,
    ModmailService,
    ModmailUserNotFoundError,
)
from bot.services.modmail_ws import modmail_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modmail", tags=["modmail"])


class SendMessageRequest(BaseModel):
    """Request body for sending a modmail message."""

    message: str


@router.get("/conversations", dependencies=[Depends(require_ride_coordinator)])
async def list_conversations():
    """
    List all modmail conversations with their latest message.

    Returns:
        JSON with a list of conversations.
    """
    async with AsyncSessionLocal() as session:
        conversations = await ModmailMessagesRepository.get_conversations(session)

        channels = {}
        for conv in conversations:
            row = await ModmailRepository.get_by_user_id(session, conv["user_id"])
            if row:
                channels[conv["user_id"]] = row.username

    for conv in conversations:
        if not conv.get("sender_name"):
            conv["sender_name"] = channels.get(conv["user_id"])
        conv["username"] = channels.get(conv["user_id"])

    return {"conversations": conversations}


@router.get(
    "/conversations/{user_id}/messages",
    dependencies=[Depends(require_ride_coordinator)],
)
async def get_messages(
    user_id: str,
    limit: int = Query(default=50, le=200),
    before_id: int | None = Query(default=None),
):
    """
    Fetch messages for a conversation.

    Args:
        user_id: The Discord user ID of the conversation owner.
        limit: Maximum messages to return.
        before_id: Cursor for pagination (return messages with id < before_id).

    Returns:
        JSON with a list of messages.
    """
    async with AsyncSessionLocal() as session:
        messages = await ModmailMessagesRepository.get_messages(
            session,
            user_id,
            limit=limit,
            before_id=before_id,
        )

    return {
        "messages": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "sender_type": m.sender_type.value,
                "sender_id": m.sender_id,
                "sender_name": m.sender_name,
                "content": m.content,
                "attachments_json": m.attachments_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.post(
    "/conversations/{user_id}/messages",
    dependencies=[Depends(require_ride_coordinator)],
)
async def send_message(
    user_id: str,
    body: SendMessageRequest,
):
    """
    Send a modmail message to a user from the web UI.

    The message is DM'd to the user and mirrored in the Discord modmail channel.

    Args:
        user_id: The target Discord user ID.
        body: Contains the message text.

    Returns:
        JSON with delivery status.
    """
    bot = require_ready_bot()
    service = ModmailService(bot)

    try:
        result = await service.dm_user(int(user_id), body.message)
    except ModmailConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except (ModmailUserNotFoundError, ModmailAmbiguousUserError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "delivered": result.delivered,
        "channel_id": str(result.channel.id),
    }


@router.websocket("/ws")
async def modmail_websocket(ws: WebSocket):
    """
    WebSocket endpoint for real-time modmail message updates.

    Clients receive JSON payloads whenever a new message is persisted.
    """
    await modmail_ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        modmail_ws_manager.disconnect(ws)
