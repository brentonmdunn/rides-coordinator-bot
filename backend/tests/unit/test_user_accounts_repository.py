"""Unit tests for UserAccountsRepository (data access layer)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import AccountRoles
from bot.core.models import UserAccount
from bot.repositories.user_accounts_repository import UserAccountsRepository


def _make_session(first_return=None, all_return=None, get_return=None):
    """Build a mock AsyncSession with pre-configured execute and get returns."""
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    result.scalars.return_value.first.return_value = first_return
    result.scalars.return_value.all.return_value = all_return or []
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=get_return)
    return session


def _make_account(**kwargs) -> UserAccount:
    account = MagicMock(spec=UserAccount)
    for k, v in kwargs.items():
        setattr(account, k, v)
    return account


# ---------------------------------------------------------------------------
# get_all_accounts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_accounts_returns_list():
    acct1 = _make_account(email="a@example.com")
    acct2 = _make_account(email="b@example.com")
    session = _make_session(all_return=[acct1, acct2])

    result = await UserAccountsRepository.get_all_accounts(session)

    assert result == [acct1, acct2]
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_all_accounts_empty():
    session = _make_session(all_return=[])
    result = await UserAccountsRepository.get_all_accounts(session)
    assert result == []


# ---------------------------------------------------------------------------
# get_by_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_email_found():
    acct = _make_account(email="user@example.com")
    session = _make_session(first_return=acct)

    result = await UserAccountsRepository.get_by_email(session, "user@example.com")

    assert result is acct
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_email_not_found():
    session = _make_session(first_return=None)
    result = await UserAccountsRepository.get_by_email(session, "missing@example.com")
    assert result is None


# ---------------------------------------------------------------------------
# get_by_discord_user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_discord_user_id_found():
    acct = _make_account(discord_user_id="123456789")
    session = _make_session(first_return=acct)

    result = await UserAccountsRepository.get_by_discord_user_id(session, "123456789")

    assert result is acct
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_discord_user_id_not_found():
    session = _make_session(first_return=None)
    result = await UserAccountsRepository.get_by_discord_user_id(session, "999")
    assert result is None


# ---------------------------------------------------------------------------
# get_by_discord_username
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_discord_username_found():
    acct = _make_account(discord_username="someuser")
    session = _make_session(first_return=acct)

    result = await UserAccountsRepository.get_by_discord_username(session, "someuser")

    assert result is acct


@pytest.mark.asyncio
async def test_get_by_discord_username_not_found():
    session = _make_session(first_return=None)
    result = await UserAccountsRepository.get_by_discord_username(session, "ghost")
    assert result is None


# ---------------------------------------------------------------------------
# get_unlinked_by_discord_username
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unlinked_by_discord_username_found():
    acct = _make_account(discord_username="newuser", discord_user_id=None)
    session = _make_session(first_return=acct)

    result = await UserAccountsRepository.get_unlinked_by_discord_username(session, "newuser")

    assert result is acct
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_unlinked_by_discord_username_not_found():
    session = _make_session(first_return=None)
    result = await UserAccountsRepository.get_unlinked_by_discord_username(session, "linkeduser")
    assert result is None


# ---------------------------------------------------------------------------
# get_unlinked_by_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_unlinked_by_email_found():
    acct = _make_account(email="old@example.com", discord_user_id=None)
    session = _make_session(first_return=acct)

    result = await UserAccountsRepository.get_unlinked_by_email(session, "old@example.com")

    assert result is acct
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_unlinked_by_email_not_found():
    session = _make_session(first_return=None)
    result = await UserAccountsRepository.get_unlinked_by_email(session, "linked@example.com")
    assert result is None


# ---------------------------------------------------------------------------
# create_account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_account_calls_add_and_commit():
    session = AsyncMock(spec=AsyncSession)
    session.refresh = AsyncMock()

    result = await UserAccountsRepository.create_account(session, "new@example.com")

    session.add.assert_called_once()
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, UserAccount)
    assert added_obj.email == "new@example.com"
    assert added_obj.role == AccountRoles.VIEWER
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added_obj)
    assert result is added_obj


@pytest.mark.asyncio
async def test_create_account_with_custom_role():
    session = AsyncMock(spec=AsyncSession)
    session.refresh = AsyncMock()

    result = await UserAccountsRepository.create_account(
        session, "admin@example.com", AccountRoles.ADMIN
    )

    added_obj = session.add.call_args[0][0]
    assert added_obj.role == AccountRoles.ADMIN


# ---------------------------------------------------------------------------
# get_or_create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_create_existing_account():
    existing = _make_account(email="existing@example.com")
    session = _make_session(first_return=existing)

    result = await UserAccountsRepository.get_or_create(session, "existing@example.com")

    assert result is existing
    # commit should NOT be called since we just fetched
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_creates_when_missing():
    session = AsyncMock(spec=AsyncSession)
    session.refresh = AsyncMock()

    # execute returns None (not found)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    result = await UserAccountsRepository.get_or_create(session, "brand_new@example.com")

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert isinstance(result, UserAccount)


# ---------------------------------------------------------------------------
# create_invited
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_invited_calls_add_and_commit():
    session = AsyncMock(spec=AsyncSession)
    session.refresh = AsyncMock()

    result = await UserAccountsRepository.create_invited(
        session,
        discord_username="invitee",
        role=AccountRoles.VIEWER,
        invited_by="admin@example.com",
    )

    session.add.assert_called_once()
    added_obj = session.add.call_args[0][0]
    assert isinstance(added_obj, UserAccount)
    assert added_obj.discord_username == "invitee"
    assert added_obj.invited_by == "admin@example.com"
    assert added_obj.email is None
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(added_obj)
    assert result is added_obj


# ---------------------------------------------------------------------------
# delete_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_by_id_found_returns_true():
    acct = _make_account(id=42)
    session = _make_session(get_return=acct)
    session.delete = AsyncMock()

    result = await UserAccountsRepository.delete_by_id(session, 42)

    assert result is True
    session.delete.assert_awaited_once_with(acct)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_by_id_not_found_returns_false():
    session = _make_session(get_return=None)
    session.delete = AsyncMock()

    result = await UserAccountsRepository.delete_by_id(session, 999)

    assert result is False
    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# update_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_role_returns_updated_account():
    updated_acct = _make_account(email="user@example.com", role=AccountRoles.ADMIN)
    session = _make_session(first_return=updated_acct)

    result = await UserAccountsRepository.update_role(
        session, "user@example.com", AccountRoles.ADMIN, role_edited_by="admin@example.com"
    )

    assert result is updated_acct
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_role_returns_none_when_not_found():
    session = _make_session(first_return=None)

    result = await UserAccountsRepository.update_role(
        session, "ghost@example.com", AccountRoles.ADMIN
    )

    assert result is None
    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# link_discord_identity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_link_discord_identity_returns_updated_account():
    updated_acct = _make_account(
        id=7,
        discord_user_id="111",
        discord_username="newhandle",
        email="linked@example.com",
    )
    session = _make_session(first_return=updated_acct)

    result = await UserAccountsRepository.link_discord_identity(
        session,
        account_id=7,
        discord_user_id="111",
        discord_username="newhandle",
        email="linked@example.com",
    )

    assert result is updated_acct
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_link_discord_identity_no_email():
    """When email=None the email key should not appear in the update values."""
    updated_acct = _make_account(id=8, discord_user_id="222", discord_username="handle2")
    session = _make_session(first_return=updated_acct)

    result = await UserAccountsRepository.link_discord_identity(
        session,
        account_id=8,
        discord_user_id="222",
        discord_username="handle2",
        email=None,
    )

    assert result is updated_acct
    session.commit.assert_awaited_once()
