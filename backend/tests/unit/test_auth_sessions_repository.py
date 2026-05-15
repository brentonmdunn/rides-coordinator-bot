"""Unit tests for AuthSessionsRepository (data access layer)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.repositories.auth_sessions_repository import AuthSessionsRepository


def _make_session(scalars_first=None, rowcount=0):
    """Build a mock AsyncSession with configurable execute return values."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.first.return_value = scalars_first
    result.rowcount = rowcount
    session.execute = AsyncMock(return_value=result)
    return session, result


@pytest.mark.asyncio
async def test_create_returns_auth_session():
    """create() should add, commit, refresh, and return the session object."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    expires = datetime.utcnow() + timedelta(days=30)

    result = await AuthSessionsRepository.create(
        session,
        session_id_hash="abc123",
        email="user@example.com",
        csrf_token="csrf-xyz",
        expires_at=expires,
    )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once()
    # The object passed to add and returned should be the same AuthSession
    added_obj = session.add.call_args[0][0]
    assert added_obj.session_id_hash == "abc123"
    assert added_obj.email == "user@example.com"
    assert added_obj.csrf_token == "csrf-xyz"
    assert added_obj.expires_at == expires
    assert result is added_obj


@pytest.mark.asyncio
async def test_get_by_hash_found():
    """get_by_hash() should return the session row when found."""
    mock_row = Mock()
    mock_row.session_id_hash = "hash-abc"
    session, _ = _make_session(scalars_first=mock_row)

    result = await AuthSessionsRepository.get_by_hash(session, "hash-abc")

    session.execute.assert_awaited_once()
    assert result is mock_row


@pytest.mark.asyncio
async def test_get_by_hash_not_found():
    """get_by_hash() should return None when no session row exists."""
    session, _ = _make_session(scalars_first=None)

    result = await AuthSessionsRepository.get_by_hash(session, "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_update_activity_executes_and_commits():
    """update_activity() should execute an update statement and commit."""
    session, _ = _make_session()
    now = datetime.utcnow()
    new_expires = now + timedelta(days=30)

    await AuthSessionsRepository.update_activity(
        session,
        session_id_hash="hash-abc",
        last_activity_at=now,
        expires_at=new_expires,
    )

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_hash_executes_and_commits():
    """delete_by_hash() should execute a delete statement and commit."""
    session, _ = _make_session()

    await AuthSessionsRepository.delete_by_hash(session, "hash-abc")

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_email_returns_rowcount():
    """delete_by_email() should return the number of deleted rows."""
    session, _ = _make_session(rowcount=3)

    count = await AuthSessionsRepository.delete_by_email(session, "user@example.com")

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert count == 3


@pytest.mark.asyncio
async def test_delete_by_email_returns_zero_when_none():
    """delete_by_email() should return 0 when no sessions exist for the email."""
    session, _ = _make_session(rowcount=0)

    count = await AuthSessionsRepository.delete_by_email(session, "nobody@example.com")

    assert count == 0


@pytest.mark.asyncio
async def test_delete_expired_returns_rowcount():
    """delete_expired() should delete expired sessions and return the count."""
    session, _ = _make_session(rowcount=5)

    count = await AuthSessionsRepository.delete_expired(session)

    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()
    assert count == 5


@pytest.mark.asyncio
async def test_delete_expired_returns_zero_when_none():
    """delete_expired() should return 0 when no expired sessions exist."""
    session, _ = _make_session(rowcount=0)

    count = await AuthSessionsRepository.delete_expired(session)

    assert count == 0
