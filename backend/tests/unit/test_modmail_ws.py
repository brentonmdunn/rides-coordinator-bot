"""Unit tests for ModmailWSManager."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bot.services.modmail_ws import ModmailWSManager


class TestModmailWSManagerConnect:
    """Tests for ModmailWSManager.connect."""

    @pytest.mark.asyncio
    async def test_connect_accepts_and_registers(self):
        manager = ModmailWSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        await manager.connect(ws)

        ws.accept.assert_awaited_once()
        assert ws in manager._connections

    @pytest.mark.asyncio
    async def test_connect_multiple_clients(self):
        manager = ModmailWSManager()
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        assert len(manager._connections) == 2


class TestModmailWSManagerDisconnect:
    """Tests for ModmailWSManager.disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        manager = ModmailWSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        await manager.connect(ws)
        assert ws in manager._connections

        manager.disconnect(ws)
        assert ws not in manager._connections

    def test_disconnect_unknown_ws_does_not_raise(self):
        """Discarding a connection that was never added should be a no-op."""
        manager = ModmailWSManager()
        ws = MagicMock()

        # Should not raise
        manager.disconnect(ws)

    @pytest.mark.asyncio
    async def test_disconnect_only_removes_specified(self):
        manager = ModmailWSManager()
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        manager.disconnect(ws1)

        assert ws1 not in manager._connections
        assert ws2 in manager._connections


class TestModmailWSManagerBroadcast:
    """Tests for ModmailWSManager.broadcast."""

    @pytest.mark.asyncio
    async def test_broadcasts_to_all_connections(self):
        import json

        manager = ModmailWSManager()
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        data = {"type": "new_message", "content": "hello"}
        await manager.broadcast(data)

        expected = json.dumps(data)
        ws1.send_text.assert_awaited_once_with(expected)
        ws2.send_text.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections_does_nothing(self):
        manager = ModmailWSManager()
        # Should not raise
        await manager.broadcast({"type": "ping"})

    @pytest.mark.asyncio
    async def test_broken_connection_removed_on_broadcast(self):
        manager = ModmailWSManager()
        ws_good = MagicMock()
        ws_good.accept = AsyncMock()
        ws_good.send_text = AsyncMock()

        ws_broken = MagicMock()
        ws_broken.accept = AsyncMock()
        ws_broken.send_text = AsyncMock(side_effect=RuntimeError("connection lost"))

        await manager.connect(ws_good)
        await manager.connect(ws_broken)

        await manager.broadcast({"type": "ping"})

        # Broken connection should be removed
        assert ws_broken not in manager._connections
        # Good connection should still receive messages
        ws_good.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_serializes_nested_dict(self):
        import json

        manager = ModmailWSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()

        await manager.connect(ws)

        data = {"type": "new_message", "message": {"id": 1, "content": "hi"}}
        await manager.broadcast(data)

        ws.send_text.assert_awaited_once_with(json.dumps(data))

    @pytest.mark.asyncio
    async def test_connection_count_after_disconnect(self):
        manager = ModmailWSManager()
        ws = MagicMock()
        ws.accept = AsyncMock()

        await manager.connect(ws)
        assert len(manager._connections) == 1
        manager.disconnect(ws)
        assert len(manager._connections) == 0
