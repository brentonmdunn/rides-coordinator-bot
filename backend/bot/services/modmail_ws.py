"""WebSocket connection manager for modmail real-time updates."""

from __future__ import annotations

import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ModmailWSManager:
    """Manages WebSocket connections for the modmail chat UI."""

    def __init__(self) -> None:
        """Initialize the manager with an empty connection set."""
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        """
        Accept and register a new WebSocket connection.

        Args:
            ws: The WebSocket connection to register.
        """
        await ws.accept()
        self._connections.add(ws)
        logger.info("Modmail WS connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        """
        Remove a WebSocket connection from the manager.

        Args:
            ws: The WebSocket connection to remove.
        """
        self._connections.discard(ws)
        logger.info("Modmail WS disconnected (%d total)", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        """
        Send a JSON message to all connected WebSocket clients.

        Broken connections are silently removed.

        Args:
            data: The dictionary payload to broadcast.
        """
        payload = json.dumps(data)
        broken: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                broken.append(ws)
        for ws in broken:
            self._connections.discard(ws)


modmail_ws_manager = ModmailWSManager()
