"""Unit tests for AuthService — identity matching cascade and session helpers."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from bot.core.enums import AccountRoles
from bot.core.models import AuthSession, UserAccount
from bot.services.auth_service import TOUCH_THROTTLE_MINUTES, AuthService, _hash_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(
    id: int = 1,
    email: str | None = "user@example.com",
    discord_user_id: str | None = None,
    discord_username: str | None = None,
    role: AccountRoles = AccountRoles.VIEWER,
) -> UserAccount:
    account = MagicMock(spec=UserAccount)
    account.id = id
    account.email = email
    account.discord_user_id = discord_user_id
    account.discord_username = discord_username
    account.role = role
    return account


def _make_session(
    email: str = "user@example.com",
    expires_at: datetime | None = None,
    last_activity_at: datetime | None = None,
) -> AuthSession:
    s = MagicMock(spec=AuthSession)
    s.email = email
    s.expires_at = expires_at or (datetime.utcnow() + timedelta(days=30))
    s.last_activity_at = last_activity_at or datetime.utcnow()
    s.csrf_token = "csrf-token-value"
    return s


# ---------------------------------------------------------------------------
# _hash_token
# ---------------------------------------------------------------------------


def test_hash_token_is_sha256():
    token = "abc123"
    assert _hash_token(token) == hashlib.sha256(token.encode()).hexdigest()


def test_hash_token_deterministic():
    assert _hash_token("x") == _hash_token("x")


def test_hash_token_unique():
    assert _hash_token("a") != _hash_token("b")


# ---------------------------------------------------------------------------
# verify_csrf
# ---------------------------------------------------------------------------


def test_verify_csrf_matching():
    assert AuthService.verify_csrf("secret", "secret") is True


def test_verify_csrf_mismatch():
    assert AuthService.verify_csrf("secret", "wrong") is False


def test_verify_csrf_none_provided():
    assert AuthService.verify_csrf("secret", None) is False


def test_verify_csrf_empty_string():
    assert AuthService.verify_csrf("secret", "") is False


# ---------------------------------------------------------------------------
# match_or_reject — branch 1: already linked by discord_user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_branch1_returns_existing_account():
    account = _make_account(discord_user_id="u123")
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
        new=AsyncMock(return_value=account),
    ):
        result = await AuthService.match_or_reject(session, "u123", "username", "u@e.com")

    assert result is account


@pytest.mark.asyncio
async def test_match_branch1_skips_further_branches():
    account = _make_account(discord_user_id="u123")
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=None),
        ) as mock_branch2,
    ):
        await AuthService.match_or_reject(session, "u123", "username", "u@e.com")

    mock_branch2.assert_not_called()


# ---------------------------------------------------------------------------
# match_or_reject — branch 2: unlinked by discord username
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_branch2_links_and_returns():
    unlinked = _make_account(id=5, discord_user_id=None, discord_username="alice")
    linked = _make_account(id=5, discord_user_id="u999", discord_username="alice")
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=unlinked),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.link_discord_identity",
            new=AsyncMock(return_value=linked),
        ),
    ):
        result = await AuthService.match_or_reject(session, "u999", "alice", "a@e.com")

    assert result is linked


@pytest.mark.asyncio
async def test_match_branch2_race_condition_falls_back_to_branch1():
    """If link raises IntegrityError, re-fetch by discord_user_id."""
    unlinked = _make_account(id=5, discord_user_id=None, discord_username="alice")
    recovered = _make_account(id=5, discord_user_id="u999")
    session = AsyncMock()

    get_by_id_returns = [None, recovered]

    async def get_by_id(s, uid):
        return get_by_id_returns.pop(0)

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id", new=get_by_id
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=unlinked),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.link_discord_identity",
            new=AsyncMock(side_effect=IntegrityError(None, None, None)),
        ),
    ):
        result = await AuthService.match_or_reject(session, "u999", "alice", "a@e.com")

    session.rollback.assert_awaited_once()
    assert result is recovered


# ---------------------------------------------------------------------------
# match_or_reject — branch 3: grandfather by email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_branch3_grandfather_links_and_returns():
    unlinked = _make_account(id=7, email="old@cf.com", discord_user_id=None)
    linked = _make_account(id=7, email="old@cf.com", discord_user_id="u111")
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_email",
            new=AsyncMock(return_value=unlinked),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.link_discord_identity",
            new=AsyncMock(return_value=linked),
        ),
    ):
        result = await AuthService.match_or_reject(session, "u111", "newname", "old@cf.com")

    assert result is linked


@pytest.mark.asyncio
async def test_match_branch3_skipped_when_no_email():
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_email",
            new=AsyncMock(return_value=None),
        ) as mock_email_lookup,
    ):
        result = await AuthService.match_or_reject(session, "u111", "newname", None)

    mock_email_lookup.assert_not_called()
    assert result is None


# ---------------------------------------------------------------------------
# match_or_reject — no match
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_returns_none_when_not_invited():
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_discord_username",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_unlinked_by_email",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await AuthService.match_or_reject(session, "u999", "stranger", "x@x.com")

    assert result is None


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_returns_plaintext_and_csrf():
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.create",
        new=AsyncMock(return_value=MagicMock()),
    ) as mock_create:
        session_id, csrf = await AuthService.create_session(session, "u@e.com")

    assert len(session_id) > 0
    assert len(csrf) > 0
    assert session_id != csrf
    args = mock_create.call_args
    # Stored value should be the hash, not the plaintext
    assert args[0][1] == _hash_token(session_id)
    assert args[0][2] == "u@e.com"
    assert args[0][3] == csrf


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_session_valid_returns_auth_session():
    auth_session = _make_session()
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.get_by_hash",
        new=AsyncMock(return_value=auth_session),
    ):
        result = await AuthService.get_session(session, "plain-token")

    assert result is auth_session


@pytest.mark.asyncio
async def test_get_session_not_found_returns_none():
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.get_by_hash",
        new=AsyncMock(return_value=None),
    ):
        result = await AuthService.get_session(session, "missing")

    assert result is None


@pytest.mark.asyncio
async def test_get_session_expired_deletes_and_returns_none():
    expired = _make_session(expires_at=datetime.utcnow() - timedelta(seconds=1))
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.AuthSessionsRepository.get_by_hash",
            new=AsyncMock(return_value=expired),
        ),
        patch(
            "bot.services.auth_service.AuthSessionsRepository.delete_by_hash",
            new=AsyncMock(),
        ) as mock_delete,
    ):
        result = await AuthService.get_session(session, "plain-token")

    assert result is None
    mock_delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# touch_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_touch_session_slides_expiry_when_stale():
    old_activity = datetime.utcnow() - timedelta(minutes=TOUCH_THROTTLE_MINUTES + 1)
    auth_session = _make_session(last_activity_at=old_activity)
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.update_activity",
        new=AsyncMock(),
    ) as mock_update:
        await AuthService.touch_session(session, "plain-token", auth_session)

    mock_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_touch_session_skips_when_recent():
    recent_activity = datetime.utcnow() - timedelta(seconds=30)
    auth_session = _make_session(last_activity_at=recent_activity)
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.update_activity",
        new=AsyncMock(),
    ) as mock_update:
        await AuthService.touch_session(session, "plain-token", auth_session)

    mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# revoke_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_session_deletes_by_hash():
    session = AsyncMock()

    with patch(
        "bot.services.auth_service.AuthSessionsRepository.delete_by_hash",
        new=AsyncMock(),
    ) as mock_delete:
        await AuthService.revoke_session(session, "plain-token")

    mock_delete.assert_awaited_once_with(session, _hash_token("plain-token"))


# ---------------------------------------------------------------------------
# provision_from_guild_role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_provision_from_guild_role_creates_ride_coordinator():
    created = _make_account(
        id=10, email="u@discord.placeholder", role=AccountRoles.RIDE_COORDINATOR
    )
    linked = _make_account(id=10, discord_user_id="u42", role=AccountRoles.RIDE_COORDINATOR)
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.create_account",
            new=AsyncMock(return_value=created),
        ) as mock_create,
        patch(
            "bot.services.auth_service.UserAccountsRepository.link_discord_identity",
            new=AsyncMock(return_value=linked),
        ),
    ):
        result = await AuthService.provision_from_guild_role(session, "u42", "rider", None)

    assert result is linked
    assert mock_create.call_args[1]["role"] == AccountRoles.RIDE_COORDINATOR


@pytest.mark.asyncio
async def test_provision_from_guild_role_uses_real_email_when_available():
    created = _make_account(id=10, email="real@email.com", role=AccountRoles.RIDE_COORDINATOR)
    linked = _make_account(id=10, discord_user_id="u42", role=AccountRoles.RIDE_COORDINATOR)
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.create_account",
            new=AsyncMock(return_value=created),
        ) as mock_create,
        patch(
            "bot.services.auth_service.UserAccountsRepository.link_discord_identity",
            new=AsyncMock(return_value=linked),
        ),
    ):
        await AuthService.provision_from_guild_role(session, "u42", "rider", "real@email.com")

    assert mock_create.call_args[1]["email"] == "real@email.com"


@pytest.mark.asyncio
async def test_provision_from_guild_role_race_condition_recovers():
    recovered = _make_account(id=10, discord_user_id="u42")
    session = AsyncMock()

    with (
        patch(
            "bot.services.auth_service.UserAccountsRepository.create_account",
            new=AsyncMock(side_effect=IntegrityError(None, None, None)),
        ),
        patch(
            "bot.services.auth_service.UserAccountsRepository.get_by_discord_user_id",
            new=AsyncMock(return_value=recovered),
        ),
    ):
        result = await AuthService.provision_from_guild_role(session, "u42", "rider", None)

    session.rollback.assert_awaited_once()
    assert result is recovered
