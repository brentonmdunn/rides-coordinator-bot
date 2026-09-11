"""
User preferences service.

Business logic layer for per-user UI/app preferences.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.database import AsyncSessionLocal
from bot.core.models import UserPreferences
from bot.repositories.user_preferences_repository import UserPreferencesRepository


class UserPreferencesService:
    """Service for managing user preferences."""

    @staticmethod
    async def get_preferences(email: str, session: AsyncSession | None = None) -> UserPreferences:
        """
        Get preferences for a user, creating defaults on first access.

        Args:
            email: The user's email address.
            session: Optional database session. If None, one is created internally.

        Returns:
            The user's UserPreferences (never None — defaults are created if missing).
        """
        if session is not None:
            return await UserPreferencesRepository.get_or_create(session, email)

        async with AsyncSessionLocal() as session:
            return await UserPreferencesRepository.get_or_create(session, email)

    @staticmethod
    async def set_show_map_labels(
        email: str, value: bool, session: AsyncSession | None = None
    ) -> UserPreferences | None:
        """
        Update the show_map_labels preference for a user.

        Args:
            email: The user's email address.
            value: True to show map labels, False to hide them.
            session: Optional database session. If None, one is created internally.

        Returns:
            The updated UserPreferences, or None if the user has no preferences row yet.
        """
        if session is not None:
            return await UserPreferencesRepository.update_preferences(
                session, email, show_map_labels=value
            )

        async with AsyncSessionLocal() as session:
            return await UserPreferencesRepository.update_preferences(
                session, email, show_map_labels=value
            )
