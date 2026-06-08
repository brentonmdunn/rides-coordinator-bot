"""Unit tests for ThreadService.create_event_thread_from_message."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from bot.services.thread_service import ThreadService

pytestmark = pytest.mark.asyncio


def _session_cm():
    mock_session = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, mock_session


async def test_creates_new_thread_when_message_has_none():
    """When the message has no thread, one is created, registered, and reactors added."""
    thread = MagicMock(spec=discord.Thread)
    thread.id = 555

    message = MagicMock(spec=discord.Message)
    message.id = 555
    message.thread = None
    message.create_thread = AsyncMock(return_value=thread)

    svc = ThreadService()
    svc.bulk_add_reactors_to_thread = AsyncMock(return_value=(["alice"], []))

    cm, _ = _session_cm()
    with (
        patch("bot.services.thread_service.AsyncSessionLocal", return_value=cm),
        patch(
            "bot.services.thread_service.EventThreadRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "bot.services.thread_service.EventThreadRepository.create",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        result_thread, added, failed = await svc.create_event_thread_from_message(
            message, "My Thread"
        )

    message.create_thread.assert_awaited_once_with(name="My Thread")
    svc.bulk_add_reactors_to_thread.assert_awaited_once_with(thread)
    mock_create.assert_awaited_once()
    assert result_thread is thread
    assert added == ["alice"]
    assert failed == []


async def test_reuses_existing_thread_and_registers():
    """When the message already has a thread, it is registered and reactors added."""
    existing_thread = MagicMock(spec=discord.Thread)
    existing_thread.id = 777

    message = MagicMock(spec=discord.Message)
    message.id = 777
    message.thread = existing_thread
    message.create_thread = AsyncMock()

    svc = ThreadService()
    svc.bulk_add_reactors_to_thread = AsyncMock(return_value=(["bob"], ["carol"]))

    cm, _ = _session_cm()
    with (
        patch("bot.services.thread_service.AsyncSessionLocal", return_value=cm),
        patch(
            "bot.services.thread_service.EventThreadRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "bot.services.thread_service.EventThreadRepository.create",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        result_thread, added, _failed = await svc.create_event_thread_from_message(
            message, "Ignored Name"
        )

    message.create_thread.assert_not_awaited()
    svc.bulk_add_reactors_to_thread.assert_awaited_once_with(existing_thread)
    mock_create.assert_awaited_once()
    assert result_thread is existing_thread
    assert added == ["bob"]


async def test_already_tracked_thread_is_idempotent():
    """An already-registered thread is not re-created in the DB, only reactors added."""
    existing_thread = MagicMock(spec=discord.Thread)
    existing_thread.id = 999

    message = MagicMock(spec=discord.Message)
    message.id = 999
    message.thread = existing_thread

    svc = ThreadService()
    svc.bulk_add_reactors_to_thread = AsyncMock(return_value=([], []))

    cm, _ = _session_cm()
    with (
        patch("bot.services.thread_service.AsyncSessionLocal", return_value=cm),
        patch(
            "bot.services.thread_service.EventThreadRepository.get_by_id",
            new_callable=AsyncMock,
            return_value=MagicMock(),  # already tracked
        ),
        patch(
            "bot.services.thread_service.EventThreadRepository.create",
            new_callable=AsyncMock,
        ) as mock_create,
    ):
        await svc.create_event_thread_from_message(message, "Name")

    mock_create.assert_not_awaited()
    svc.bulk_add_reactors_to_thread.assert_awaited_once_with(existing_thread)
