"""
Service for the people roster (the ``locations`` table).

Single source of truth for creating, editing, deleting, and self-registering the
people the bot gives rides to. Used by both the ``/api/roster`` routes and the
Discord registration view.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from shared.core.enums import CampusLivingLocations, ClassYear

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Person:
    """A roster entry."""

    id: int
    name: str
    discord_username: str | None
    discord_user_id: str | None
    year: str | None
    location: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class PersonInput:
    """Fields for creating a roster entry."""

    name: str
    discord_username: str | None = None
    year: str | None = None
    location: str | None = None


UPDATABLE_FIELDS: frozenset[str] = frozenset({"name", "discord_username", "year", "location"})


class RosterService:
    """Business logic for the people roster."""

    @staticmethod
    async def list_people() -> list[Person]:
        """Return every roster entry, ordered by name (case-insensitive)."""
        raise NotImplementedError

    @staticmethod
    async def get_person(person_id: int) -> Person:
        """
        Return one roster entry.

        Raises:
            RosterNotFoundError: If no entry has ``person_id``.
        """
        raise NotImplementedError

    @staticmethod
    async def create_person(data: PersonInput) -> Person:
        """
        Create a roster entry.

        Raises:
            RosterValidationError: If a field is invalid.
            RosterConflictError: If the Discord username is already on the roster.
        """
        raise NotImplementedError

    @staticmethod
    async def update_person(person_id: int, changes: dict[str, str | None]) -> Person:
        """
        Apply a partial update to a roster entry.

        Only keys present in ``changes`` are applied; keys must be in ``UPDATABLE_FIELDS``.

        Raises:
            RosterNotFoundError: If no entry has ``person_id``.
            RosterValidationError: If a key or value is invalid.
            RosterConflictError: If the Discord username is already on the roster.
        """
        raise NotImplementedError

    @staticmethod
    async def delete_people(person_ids: list[int]) -> int:
        """Delete roster entries by id and return how many were deleted (unknown ids ignored)."""
        raise NotImplementedError

    @staticmethod
    async def register_from_discord(
        *, discord_user_id: int, discord_username: str, name: str, year: str, location: str
    ) -> tuple[Person, bool]:
        """
        Create or update the roster entry for a Discord member.

        Returns:
            ``(person, created)``.

        Raises:
            RosterValidationError: If a field is invalid.
            RosterConflictError: If the username belongs to a row linked to another account.
        """
        raise NotImplementedError

    @staticmethod
    async def find_member(*, discord_user_id: int, discord_username: str) -> Person | None:
        """
        Find a member's roster entry, refreshing a changed username or linking an unlinked row.

        Returns:
            The entry, or ``None`` if the member is not registered.
        """
        raise NotImplementedError

    @staticmethod
    def get_options() -> dict[str, list[str]]:
        """Return the valid class years and living locations for roster forms."""
        return {
            "years": [year.value for year in ClassYear],
            "locations": [location.value for location in CampusLivingLocations],
        }
