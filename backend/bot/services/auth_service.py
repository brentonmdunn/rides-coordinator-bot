"""
Auth service.

Business logic for Discord OAuth identity matching and server-side session management.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import AuthSession, UserAccount
from bot.repositories.auth_sessions_repository import AuthSessionsRepository
from bot.repositories.user_accounts_repository import UserAccountsRepository

SESSION_TTL_DAYS = 30
TOUCH_THROTTLE_MINUTES = 5


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    """Service for Discord OAuth matching and session lifecycle."""

    @staticmethod
    async def match_or_reject(
        session: AsyncSession,
        discord_user_id: str,
        discord_username: str,
        email: str | None,
    ) -> UserAccount | None:
        """
        3-tier cascade:
          1. By discord_user_id (stable, linked on previous login)
          2. By discord_username where discord_user_id IS NULL (first login, invited by username)
          3. By email where discord_user_id IS NULL (grandfather path for pre-existing accounts)

        After matching via branch 2 or 3, the account is linked with the Discord identity.
        Returns None if no match is found (user not invited).
        """
        # Branch 1: already linked
        account = await UserAccountsRepository.get_by_discord_user_id(session, discord_user_id)
        if account:
            return account

        # Branch 2: invited by Discord username, not yet linked
        account = await UserAccountsRepository.get_unlinked_by_discord_username(
            session, discord_username
        )
        if account:
            try:
                return await UserAccountsRepository.link_discord_identity(
                    session, account.id, discord_user_id, discord_username, email
                )
            except IntegrityError:
                await session.rollback()
                # Another concurrent login won the race; re-fetch by ID
                return await UserAccountsRepository.get_by_discord_user_id(session, discord_user_id)

        # Branch 3: grandfather — email-only account from CF Access era
        if email:
            account = await UserAccountsRepository.get_unlinked_by_email(session, email)
            if account:
                try:
                    return await UserAccountsRepository.link_discord_identity(
                        session, account.id, discord_user_id, discord_username, email
                    )
                except IntegrityError:
                    await session.rollback()
                    return await UserAccountsRepository.get_by_discord_user_id(
                        session, discord_user_id
                    )

        return None

    @staticmethod
    async def create_session(session: AsyncSession, email: str) -> tuple[str, str]:
        """
        Create a new server-side session.

        Returns:
            (session_id_plaintext, csrf_token) — session_id goes in the httpOnly cookie;
            csrf_token goes in the readable cookie and is verified on mutations.
        """
        session_id_plain = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_id_hash = _hash_token(session_id_plain)
        expires_at = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)

        await AuthSessionsRepository.create(session, session_id_hash, email, csrf_token, expires_at)
        return session_id_plain, csrf_token

    @staticmethod
    async def get_session(session: AsyncSession, session_id_plain: str) -> AuthSession | None:
        """
        Validate a session by plaintext token.

        Returns the AuthSession if valid and not expired, None otherwise.
        Does NOT slide the expiry — call touch_session separately for that.
        """
        session_id_hash = _hash_token(session_id_plain)
        auth_session = await AuthSessionsRepository.get_by_hash(session, session_id_hash)
        if not auth_session:
            return None
        if auth_session.expires_at < datetime.utcnow():
            await AuthSessionsRepository.delete_by_hash(session, session_id_hash)
            return None
        return auth_session

    @staticmethod
    async def touch_session(
        session: AsyncSession, session_id_plain: str, auth_session: AuthSession
    ) -> None:
        """Slide the session expiry if it hasn't been touched recently."""
        now = datetime.utcnow()
        if (now - auth_session.last_activity_at) < timedelta(minutes=TOUCH_THROTTLE_MINUTES):
            return
        new_expires = now + timedelta(days=SESSION_TTL_DAYS)
        session_id_hash = _hash_token(session_id_plain)
        await AuthSessionsRepository.update_activity(session, session_id_hash, now, new_expires)

    @staticmethod
    async def revoke_session(session: AsyncSession, session_id_plain: str) -> None:
        """Revoke a session by deleting it from the database."""
        session_id_hash = _hash_token(session_id_plain)
        await AuthSessionsRepository.delete_by_hash(session, session_id_hash)

    @staticmethod
    def verify_csrf(expected: str, provided: str | None) -> bool:
        """Constant-time CSRF token comparison."""
        if not provided:
            return False
        return hmac.compare_digest(expected, provided)
