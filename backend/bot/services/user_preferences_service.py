"""
User preferences service.

Business logic layer for per-user UI/app preferences.
"""

from bot.core.database import AsyncSessionLocal
from bot.core.models import UserPreferences
from bot.repositories.user_preferences_repository import UserPreferencesRepository


class UserPreferencesService:
    """Service for managing user preferences."""

    @staticmethod
    async def get_preferences(email: str) -> UserPreferences:
        """
        Get preferences for a user, creating defaults on first access.

        Args:
            email: The user's email address.

        Returns:
            The user's UserPreferences (never None — defaults are created if missing).
        """
        async with AsyncSessionLocal() as session:
            return await UserPreferencesRepository.get_or_create(session, email)

    @staticmethod
    async def set_show_map_labels(email: str, value: bool) -> UserPreferences | None:
        """
        Update the show_map_labels preference for a user.

        Args:
            email: The user's email address.
            value: True to show map labels, False to hide them.

        Returns:
            The updated UserPreferences, or None if the user has no preferences row yet.
        """
        async with AsyncSessionLocal() as session:
            return await UserPreferencesRepository.update_preferences(
                session, email, show_map_labels=value
            )
