"""Module-level asyncio pub/sub for ride reaction events."""

import asyncio
import logging

logger = logging.getLogger(__name__)

_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    """Register a new subscriber and return its queue."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.add(q)
    logger.debug("reaction_broadcaster: subscriber added (total=%d)", len(_subscribers))
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    _subscribers.discard(q)
    logger.debug("reaction_broadcaster: subscriber removed (total=%d)", len(_subscribers))


async def publish(event: dict) -> None:
    """Broadcast an event dict to all current subscribers."""
    if not _subscribers:
        return
    logger.debug("reaction_broadcaster: publishing to %d subscribers", len(_subscribers))
    for q in list(_subscribers):
        try:
            await q.put(event)
        except Exception:
            logger.exception("reaction_broadcaster: failed to put event on queue")
