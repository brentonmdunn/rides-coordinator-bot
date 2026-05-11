"""
Reaction Log Stream Endpoint

GET /api/reaction-log/stream — SSE stream of live ride reaction events.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.auth import require_ride_coordinator
from bot.core import reaction_broadcaster

logger = logging.getLogger(__name__)

router = APIRouter()

_HEARTBEAT_INTERVAL = 30


@router.get(
    "/api/reaction-log/stream",
    dependencies=[Depends(require_ride_coordinator)],
)
async def reaction_log_stream() -> StreamingResponse:
    """
    SSE stream of live ride reaction events.

    Yields a JSON data frame for each new event and a heartbeat comment
    every 30 seconds to keep the connection alive through proxies.
    """

    async def event_generator():
        q = reaction_broadcaster.subscribe()
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=_HEARTBEAT_INTERVAL)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.debug("reaction_log_stream: client disconnected")
        finally:
            reaction_broadcaster.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
