"""User preferences repository.

Data access layer for per-user UI/app preference management.
"""

import logging

from sqlalchemy import select, update

from bot.core.database import AsyncSessionLocal
from bot.core.models import UserPreferences

logger = logging.getLogger(__name__)


class UserPreferencesRepository:
    """Repository for user preferences CRUD operations."""

    @staticmethod
    async def get_by_email(email: str) -> UserPreferences | None:
        """Get user preferences by email.

        Args:
            email: The email address to look up.

        Returns:
            UserPreferences if found, None otherwise.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserPreferences).where(UserPreferences.email == email)
            )
            return result.scalars().first()

    @staticmethod
    async def get_or_create(email: str) -> UserPreferences:
        """Get existing preferences or create a new row with defaults.

        Args:
            email: The email address to look up or create.

        Returns:
            The existing or newly created UserPreferences.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserPreferences).where(UserPreferences.email == email)
            )
            prefs = result.scalars().first()
            if prefs:
                return prefs

            prefs = UserPreferences(email=email)
            session.add(prefs)
            await session.commit()
            await session.refresh(prefs)
            logger.info(f"⚙️  Created default preferences for '{email}'")
            return prefs

    @staticmethod
    async def update_preferences(email: str, **kwargs) -> UserPreferences | None:
        """Update one or more preference fields for a user.

        Args:
            email: The email address of the user to update.
            **kwargs: Preference field names and their new values.

        Returns:
            The updated UserPreferences, or None if not found.
        """
        if not kwargs:
            return await UserPreferencesRepository.get_by_email(email)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                update(UserPreferences)
                .where(UserPreferences.email == email)
                .values(**kwargs)
                .returning(UserPreferences)
            )
            await session.commit()
            updated = result.scalars().first()
            if updated:
                logger.info(f"⚙️  Updated preferences for '{email}': {kwargs}")
            return updated
