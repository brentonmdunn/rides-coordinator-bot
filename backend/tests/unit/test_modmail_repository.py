"""Unit tests for ModmailRepository and ModmailMessagesRepository."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.core.enums import ModmailSenderType
from bot.core.models import ModmailChannels, ModmailMessages
from bot.repositories.modmail_messages_repository import ModmailMessagesRepository
from bot.repositories.modmail_repository import ModmailRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> MagicMock:
    """Return a mock AsyncSession with common attributes pre-configured."""
    session = MagicMock()
    session.get = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


def _make_channel_row(user_id: str = "111", channel_id: str = "222") -> ModmailChannels:
    row = MagicMock(spec=ModmailChannels)
    row.user_id = user_id
    row.channel_id = channel_id
    row.username = "testuser"
    return row


def _make_message_row(
    id: int = 1,
    user_id: str = "111",
    content: str = "hello",
    sender_type: ModmailSenderType = ModmailSenderType.USER,
) -> ModmailMessages:
    row = MagicMock(spec=ModmailMessages)
    row.id = id
    row.user_id = user_id
    row.content = content
    row.sender_type = sender_type
    row.sender_id = user_id
    row.sender_name = "Alice"
    row.attachments_json = None
    row.created_at = datetime(2024, 1, 1, 12, 0, 0)
    return row


# ---------------------------------------------------------------------------
# ModmailRepository tests
# ---------------------------------------------------------------------------


class TestModmailRepositoryGetByUserId:
    @pytest.mark.asyncio
    async def test_returns_row_when_found(self):
        session = _make_session()
        expected = _make_channel_row()
        session.get = AsyncMock(return_value=expected)

        result = await ModmailRepository.get_by_user_id(session, "111")

        session.get.assert_awaited_once_with(ModmailChannels, "111")
        assert result is expected

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)

        result = await ModmailRepository.get_by_user_id(session, "missing")

        assert result is None


class TestModmailRepositoryGetByChannelId:
    @pytest.mark.asyncio
    async def test_returns_row_when_found(self):
        session = _make_session()
        expected = _make_channel_row(channel_id="999")

        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=expected)
        session.execute = AsyncMock(return_value=scalar_result)

        result = await ModmailRepository.get_by_channel_id(session, "999")

        assert result is expected

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        session = _make_session()

        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=scalar_result)

        result = await ModmailRepository.get_by_channel_id(session, "nonexistent")

        assert result is None


class TestModmailRepositoryCreate:
    @pytest.mark.asyncio
    async def test_adds_and_returns_row(self):
        session = _make_session()

        row = await ModmailRepository.create(
            session,
            user_id="123",
            channel_id="456",
            username="alice",
        )

        session.add.assert_called_once_with(row)
        assert isinstance(row, ModmailChannels)
        assert row.user_id == "123"
        assert row.channel_id == "456"
        assert row.username == "alice"

    @pytest.mark.asyncio
    async def test_creates_with_none_username(self):
        session = _make_session()

        row = await ModmailRepository.create(
            session,
            user_id="123",
            channel_id="456",
            username=None,
        )

        assert row.username is None


class TestModmailRepositoryDelete:
    @pytest.mark.asyncio
    async def test_calls_session_delete(self):
        session = _make_session()
        row = _make_channel_row()

        await ModmailRepository.delete(session, row)

        session.delete.assert_awaited_once_with(row)


# ---------------------------------------------------------------------------
# ModmailMessagesRepository tests
# ---------------------------------------------------------------------------


class TestModmailMessagesRepositoryCreate:
    @pytest.mark.asyncio
    async def test_adds_and_returns_row(self):
        session = _make_session()

        row = await ModmailMessagesRepository.create(
            session,
            user_id="111",
            sender_type=ModmailSenderType.USER,
            sender_id="111",
            sender_name="Alice",
            content="hello",
        )

        session.add.assert_called_once_with(row)
        assert isinstance(row, ModmailMessages)
        assert row.user_id == "111"
        assert row.content == "hello"
        assert row.sender_type == ModmailSenderType.USER
        assert row.sender_name == "Alice"
        assert row.attachments_json is None

    @pytest.mark.asyncio
    async def test_creates_with_attachments_json(self):
        session = _make_session()

        row = await ModmailMessagesRepository.create(
            session,
            user_id="111",
            sender_type=ModmailSenderType.ADMIN,
            sender_id="222",
            sender_name="Staff",
            content="here ya go",
            attachments_json='["http://example.com/img.png"]',
        )

        assert row.attachments_json == '["http://example.com/img.png"]'

    @pytest.mark.asyncio
    async def test_creates_with_bot_sender_type(self):
        session = _make_session()

        row = await ModmailMessagesRepository.create(
            session,
            user_id="111",
            sender_type=ModmailSenderType.BOT,
            sender_id="bot",
            sender_name="AutoBot",
            content="scheduled message",
        )

        assert row.sender_type == ModmailSenderType.BOT


class TestModmailMessagesRepositoryGetMessages:
    @pytest.mark.asyncio
    async def test_returns_rows_in_order(self):
        session = _make_session()
        rows = [
            _make_message_row(id=1, content="first"),
            _make_message_row(id=2, content="second"),
        ]

        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=list(reversed(rows)))
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        session.execute = AsyncMock(return_value=result_mock)

        result = await ModmailMessagesRepository.get_messages(session, "111")

        # rows are reversed back to oldest-first
        assert result[0].content == "first"
        assert result[1].content == "second"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_messages(self):
        session = _make_session()

        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        session.execute = AsyncMock(return_value=result_mock)

        result = await ModmailMessagesRepository.get_messages(session, "nobody")

        assert result == []

    @pytest.mark.asyncio
    async def test_before_id_applied(self):
        """Passing before_id should not raise; the query is constructed correctly."""
        session = _make_session()

        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=[])
        result_mock = MagicMock()
        result_mock.scalars = MagicMock(return_value=scalars_mock)
        session.execute = AsyncMock(return_value=result_mock)

        result = await ModmailMessagesRepository.get_messages(session, "111", before_id=10)

        assert result == []
        session.execute.assert_awaited_once()


class TestModmailMessagesRepositoryGetConversations:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        session = _make_session()

        fake_row = MagicMock()
        fake_row.user_id = "111"
        fake_row.content = "latest message"
        fake_row.created_at = datetime(2024, 6, 1, 10, 0, 0)
        fake_row.sender_name = "Alice"
        fake_row.sender_type = ModmailSenderType.USER
        fake_row.message_count = 5

        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[fake_row])
        session.execute = AsyncMock(return_value=result_mock)

        conversations = await ModmailMessagesRepository.get_conversations(session)

        assert len(conversations) == 1
        conv = conversations[0]
        assert conv["user_id"] == "111"
        assert conv["last_message_content"] == "latest message"
        assert conv["sender_name"] == "Alice"
        assert conv["message_count"] == 5
        assert conv["last_message_at"] == "2024-06-01T10:00:00"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_conversations(self):
        session = _make_session()

        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[])
        session.execute = AsyncMock(return_value=result_mock)

        conversations = await ModmailMessagesRepository.get_conversations(session)

        assert conversations == []

    @pytest.mark.asyncio
    async def test_none_created_at_produces_none_in_output(self):
        session = _make_session()

        fake_row = MagicMock()
        fake_row.user_id = "111"
        fake_row.content = "hi"
        fake_row.created_at = None
        fake_row.sender_name = "Bot"
        fake_row.sender_type = ModmailSenderType.BOT
        fake_row.message_count = 1

        result_mock = MagicMock()
        result_mock.all = MagicMock(return_value=[fake_row])
        session.execute = AsyncMock(return_value=result_mock)

        conversations = await ModmailMessagesRepository.get_conversations(session)

        assert conversations[0]["last_message_at"] is None
