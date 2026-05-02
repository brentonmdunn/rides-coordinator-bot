"""
Auth sessions repository.

Data access layer for server-side session management.
"""

import logging
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import AuthSession

logger = logging.getLogger(__name__)


class AuthSessionsRepository:
    """Repository for auth session CRUD operations."""

    @staticmethod
    async def create(
        session: AsyncSession,
        session_id_hash: str,
        email: str,
        csrf_token: str,
        expires_at: datetime,
    ) -> AuthSession:
        """Create a new auth session row."""
        auth_session = AuthSession(
            session_id_hash=session_id_hash,
            email=email,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )
        session.add(auth_session)
        await session.commit()
        await session.refresh(auth_session)
        return auth_session

    @staticmethod
    async def get_by_hash(session: AsyncSession, session_id_hash: str) -> AuthSession | None:
        """Look up a session by its hashed token."""
        result = await session.execute(
            select(AuthSession).where(AuthSession.session_id_hash == session_id_hash)
        )
        return result.scalars().first()

    @staticmethod
    async def update_activity(
        session: AsyncSession,
        session_id_hash: str,
        last_activity_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Slide the session expiry (called on each request, throttled by the service layer)."""
        await session.execute(
            update(AuthSession)
            .where(AuthSession.session_id_hash == session_id_hash)
            .values(last_activity_at=last_activity_at, expires_at=expires_at)
        )
        await session.commit()

    @staticmethod
    async def delete_by_hash(session: AsyncSession, session_id_hash: str) -> None:
        """Delete a session by its hashed token (used on logout and expiry)."""
        await session.execute(
            delete(AuthSession).where(AuthSession.session_id_hash == session_id_hash)
        )
        await session.commit()

    @staticmethod
    async def delete_expired(session: AsyncSession) -> int:
        """Delete all expired sessions and return the number of rows removed."""
        result = await session.execute(
            delete(AuthSession).where(AuthSession.expires_at < datetime.utcnow())
        )
        await session.commit()
        return result.rowcount
