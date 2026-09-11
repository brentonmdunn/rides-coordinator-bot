"""
Service layer for the main rides coordinator global setting.

Backs the `{ping}` mention used in the Sunday-service ask-rides message. The
coordinator's Discord user ID is stored in the `global_settings` table (see
`GlobalSettingsRepository`) instead of the legacy `MAIN_RIDES_COORD_USER_ID`
env var. There is deliberately no env-var fallback.
"""

import logging
from enum import Enum

import discord
from discord.ext.commands import Bot

from bot.core.database import AsyncSessionLocal
from bot.repositories.global_settings_repository import GlobalSettingsRepository
from bot.utils.format_message import ping_user

logger = logging.getLogger(__name__)

# Fallback text used when the setting is missing, malformed, or unreadable.
FALLBACK_PING_TEXT = "the rides coordinators"


class UserLookupStatus(str, Enum):
    """Outcome of a best-effort Discord user lookup."""

    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class RideCoordinatorService:
    """Reads/writes the main rides coordinator global setting."""

    COORDINATOR_KEY = "main_rides_coordinator_user_id"

    @staticmethod
    def is_valid_snowflake(value: str) -> bool:
        """Return True if value looks like a Discord snowflake ID (17-20 digits)."""
        return value.isdigit() and 17 <= len(value) <= 20

    @staticmethod
    async def get_coordinator_id() -> str | None:
        """
        Return the stored coordinator user ID, or None if unset/unreadable.

        Never raises — any DB failure (including a missing `global_settings`
        table) is logged and treated as "not configured".
        """
        try:
            async with AsyncSessionLocal() as session:
                return await GlobalSettingsRepository.get(
                    session, RideCoordinatorService.COORDINATOR_KEY
                )
        except Exception:
            logger.exception("Failed to read main rides coordinator setting")
            return None

    @staticmethod
    async def set_coordinator_id(user_id: str) -> None:
        """
        Persist the coordinator user ID.

        Args:
            user_id: The Discord user ID to store.

        Raises:
            ValueError: If user_id is not a valid Discord snowflake shape
                (all digits, 17-20 characters).
        """
        if not RideCoordinatorService.is_valid_snowflake(user_id):
            raise ValueError(
                "user_id must be a valid Discord snowflake (digits only, 17-20 characters)"
            )

        async with AsyncSessionLocal() as session:
            await GlobalSettingsRepository.set(
                session, RideCoordinatorService.COORDINATOR_KEY, user_id
            )

    @staticmethod
    async def resolve_ping_text(bot: Bot | None = None) -> tuple[str, bool]:
        """
        Resolve the `{ping}` mention text for the Sunday-service message.

        Args:
            bot: Unused for now (mention text is built from the raw ID, no
                Discord lookup is required); accepted so the signature stays
                stable if a guild-membership check (design doc failure #7) is
                added later.

        Returns:
            A tuple of (mention_text, configured). `configured` is False
            whenever the fallback text is used.
        """
        value = await RideCoordinatorService.get_coordinator_id()

        if not value or not RideCoordinatorService.is_valid_snowflake(value):
            logger.warning(
                "Main rides coordinator not configured or invalid; using fallback ping text"
            )
            return FALLBACK_PING_TEXT, False

        return ping_user(int(value)), True

    @staticmethod
    async def try_resolve_discord_user(
        bot: Bot, user_id: str
    ) -> tuple[UserLookupStatus, discord.User | None]:
        """
        Best-effort verification of a coordinator candidate against Discord.

        Args:
            bot: A ready Bot instance.
            user_id: The candidate Discord user ID (already snowflake-shaped).

        Returns:
            A tuple of (status, user). `user` is only populated when status
            is VERIFIED.
        """
        try:
            user = await bot.fetch_user(int(user_id))
        except discord.NotFound:
            return UserLookupStatus.NOT_FOUND, None
        except Exception:
            logger.exception("Could not verify Discord user id %s", user_id)
            return UserLookupStatus.UNAVAILABLE, None
        else:
            return UserLookupStatus.VERIFIED, user
