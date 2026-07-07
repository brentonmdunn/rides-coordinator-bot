"""Unit tests for AskRidesMessagesRepository."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import AskRidesMessageType
from bot.repositories.ask_rides_messages_repository import AskRidesMessagesRepository


@pytest.mark.asyncio
async def test_get_all_returns_rows():
    session = AsyncMock()
    fake_rows = [MagicMock(), MagicMock()]
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = fake_rows
    session.execute = AsyncMock(return_value=result_mock)

    rows = await AskRidesMessagesRepository.get_all(session)

    assert rows == fake_rows
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_missing():
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)

    row = await AskRidesMessagesRepository.get(session, AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

    assert row is None


@pytest.mark.asyncio
async def test_get_returns_row_when_present():
    session = AsyncMock()
    fake_row = MagicMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.one_or_none.return_value = fake_row
    session.execute = AsyncMock(return_value=result_mock)

    row = await AskRidesMessagesRepository.get(session, AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

    assert row is fake_row


@pytest.mark.asyncio
async def test_upsert_commits_and_returns_row():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    fake_row = MagicMock()
    with patch.object(
        AskRidesMessagesRepository, "get", new=AsyncMock(return_value=fake_row)
    ) as mock_get:
        row = await AskRidesMessagesRepository.upsert(
            session,
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
            "Title",
            "Body {date}",
            "teal",
            '["🪨"]',
            "user@example.com",
        )

    assert row is fake_row
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    mock_get.assert_awaited_once_with(session, AskRidesMessageType.WEDNESDAY_FELLOWSHIP)


@pytest.mark.asyncio
async def test_upsert_raises_if_readback_missing():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    with (
        patch.object(AskRidesMessagesRepository, "get", new=AsyncMock(return_value=None)),
        pytest.raises(RuntimeError),
    ):
        await AskRidesMessagesRepository.upsert(
            session,
            AskRidesMessageType.WEDNESDAY_FELLOWSHIP,
            "Title",
            "Body",
            "teal",
            None,
            "user@example.com",
        )


@pytest.mark.asyncio
async def test_delete_commits():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    await AskRidesMessagesRepository.delete(session, AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
