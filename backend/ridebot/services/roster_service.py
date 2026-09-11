"""
Service for the people roster (the ``locations`` table).

Single source of truth for creating, editing, deleting, and self-registering the
people the bot gives rides to. Used by both the ``/api/roster`` routes and the
Discord registration view.
"""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from ridebot.repositories.roster_repository import RosterRepository
from ridebot.utils.cache import invalidate_namespace
from ridebot.utils.custom_exceptions import (
    RosterConflictError,
    RosterNotFoundError,
    RosterValidationError,
)
from shared.core.database import AsyncSessionLocal
from shared.core.enums import CacheNamespace, CampusLivingLocations, ClassYear
from shared.core.models import Locations

logger = logging.getLogger(__name__)

_MAX_NAME_LENGTH = 100
_MAX_USERNAME_LENGTH = 32
_USERNAME_PATTERN = re.compile(r"^[a-z0-9_.]+$")


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


def _to_person(row: Locations) -> Person:
    """Convert a ``Locations`` ORM row into a plain ``Person``."""
    return Person(
        id=row.id,
        name=row.name,
        discord_username=row.discord_username,
        discord_user_id=row.discord_user_id,
        year=row.year,
        location=row.location,
        updated_at=row.updated_at,
    )


def _normalize_name(name: str) -> str:
    """Strip and validate a person's name."""
    cleaned = name.strip()
    if not cleaned or len(cleaned) > _MAX_NAME_LENGTH:
        raise RosterValidationError(f"Name must be between 1 and {_MAX_NAME_LENGTH} characters")
    return cleaned


def _normalize_discord_username(username: str | None) -> str | None:
    """Strip, de-@, and lowercase a Discord username; an empty string becomes ``None``."""
    if username is None:
        return None
    cleaned = username.strip().removeprefix("@").lower()
    if cleaned == "":
        return None
    if len(cleaned) > _MAX_USERNAME_LENGTH or not _USERNAME_PATTERN.match(cleaned):
        raise RosterValidationError(f"Invalid Discord username: {username!r}")
    return cleaned


def _normalize_year(year: str | None) -> str | None:
    """Match ``year`` to a canonical ``ClassYear`` value, case-insensitively."""
    if year is None:
        return None
    for candidate in ClassYear:
        if candidate.value.lower() == year.strip().lower():
            return candidate.value
    raise RosterValidationError(f"Invalid year: {year!r}")


def _normalize_location(location: str | None) -> str | None:
    """Match ``location`` to a canonical ``CampusLivingLocations`` value, case-insensitively."""
    if location is None:
        return None
    for candidate in CampusLivingLocations:
        if candidate.value.lower() == location.strip().lower():
            return candidate.value
    raise RosterValidationError(f"Invalid location: {location!r}")


async def _check_username_conflict(
    session, username: str | None, *, exclude_id: int | None = None
) -> None:
    """Raise ``RosterConflictError`` if another row already has ``username``."""
    if username is None:
        return
    existing = await RosterRepository.get_by_discord_username(session, username)
    if existing is not None and existing.id != exclude_id:
        raise RosterConflictError(f"Discord username {username!r} is already on the roster")


async def _invalidate_caches() -> None:
    """Invalidate the caches that read from the roster after a write."""
    await invalidate_namespace(CacheNamespace.ASK_RIDES_REACTIONS)
    await invalidate_namespace(CacheNamespace.ASK_DRIVERS_REACTIONS)


class RosterService:
    """Business logic for the people roster."""

    @staticmethod
    async def list_people() -> list[Person]:
        """Return every roster entry, ordered by name (case-insensitive)."""
        async with AsyncSessionLocal() as session:
            rows = await RosterRepository.get_all(session)
            return [_to_person(row) for row in rows]

    @staticmethod
    async def get_person(person_id: int) -> Person:
        """
        Return one roster entry.

        Raises:
            RosterNotFoundError: If no entry has ``person_id``.
        """
        async with AsyncSessionLocal() as session:
            row = await RosterRepository.get_by_id(session, person_id)
            if row is None:
                raise RosterNotFoundError(f"No roster entry with id {person_id}")
            return _to_person(row)

    @staticmethod
    async def create_person(data: PersonInput) -> Person:
        """
        Create a roster entry.

        Raises:
            RosterValidationError: If a field is invalid.
            RosterConflictError: If the Discord username is already on the roster.
        """
        name = _normalize_name(data.name)
        discord_username = _normalize_discord_username(data.discord_username)
        year = _normalize_year(data.year)
        location = _normalize_location(data.location)

        async with AsyncSessionLocal() as session:
            await _check_username_conflict(session, discord_username)
            row = await RosterRepository.create(
                session,
                name=name,
                discord_username=discord_username,
                discord_user_id=None,
                year=year,
                location=location,
                updated_at=datetime.now(UTC),
            )
            await session.commit()

        logger.info(f"Created roster entry id={row.id} username={discord_username}")
        await _invalidate_caches()
        return _to_person(row)

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
        unknown_keys = set(changes) - UPDATABLE_FIELDS
        if unknown_keys:
            raise RosterValidationError(f"Unknown field(s): {', '.join(sorted(unknown_keys))}")

        async with AsyncSessionLocal() as session:
            row = await RosterRepository.get_by_id(session, person_id)
            if row is None:
                raise RosterNotFoundError(f"No roster entry with id {person_id}")

            if "name" in changes:
                if changes["name"] is None:
                    raise RosterValidationError("name cannot be cleared")
                row.name = _normalize_name(changes["name"])
            if "discord_username" in changes:
                new_username = _normalize_discord_username(changes["discord_username"])
                await _check_username_conflict(session, new_username, exclude_id=person_id)
                row.discord_username = new_username
            if "year" in changes:
                row.year = _normalize_year(changes["year"])
            if "location" in changes:
                row.location = _normalize_location(changes["location"])

            row.updated_at = datetime.now(UTC)
            await session.commit()

        logger.info(f"Updated roster entry id={person_id} username={row.discord_username}")
        await _invalidate_caches()
        return _to_person(row)

    @staticmethod
    async def delete_people(person_ids: list[int]) -> int:
        """Delete roster entries by id and return how many were deleted (unknown ids ignored)."""
        async with AsyncSessionLocal() as session:
            count = await RosterRepository.delete_by_ids(session, person_ids)
            await session.commit()

        logger.info(f"Deleted {count} roster entrie(s): ids={person_ids}")
        if count:
            await _invalidate_caches()
        return count

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
        if year is None or location is None:
            raise RosterValidationError("year and location are required to register")

        normalized_name = _normalize_name(name)
        normalized_username = _normalize_discord_username(discord_username)
        normalized_year = _normalize_year(year)
        normalized_location = _normalize_location(location)
        str_discord_user_id = str(discord_user_id)

        async with AsyncSessionLocal() as session:
            row = await RosterRepository.get_by_discord_user_id(session, str_discord_user_id)
            if row is not None:
                await _check_username_conflict(session, normalized_username, exclude_id=row.id)
                row.name = normalized_name
                row.year = normalized_year
                row.location = normalized_location
                row.discord_username = normalized_username
                row.updated_at = datetime.now(UTC)
                await session.commit()
                logger.info(
                    f"Updated roster entry id={row.id} username={normalized_username} via register"
                )
                await _invalidate_caches()
                return _to_person(row), False

            existing = (
                await RosterRepository.get_by_discord_username(session, normalized_username)
                if normalized_username is not None
                else None
            )
            if existing is not None:
                if existing.discord_user_id is not None:
                    raise RosterConflictError(
                        f"Discord username {normalized_username!r} belongs to another account"
                    )
                existing.discord_user_id = str_discord_user_id
                existing.name = normalized_name
                existing.year = normalized_year
                existing.location = normalized_location
                existing.discord_username = normalized_username
                existing.updated_at = datetime.now(UTC)
                await session.commit()
                logger.info(
                    f"Claimed roster entry id={existing.id} username={normalized_username} "
                    "via register"
                )
                await _invalidate_caches()
                return _to_person(existing), False

            row = await RosterRepository.create(
                session,
                name=normalized_name,
                discord_username=normalized_username,
                discord_user_id=str_discord_user_id,
                year=normalized_year,
                location=normalized_location,
                updated_at=datetime.now(UTC),
            )
            await session.commit()

        logger.info(f"Registered new roster entry id={row.id} username={normalized_username}")
        await _invalidate_caches()
        return _to_person(row), True

    @staticmethod
    async def find_member(*, discord_user_id: int, discord_username: str) -> Person | None:
        """
        Find a member's roster entry, refreshing a changed username or linking an unlinked row.

        Returns:
            The entry, or ``None`` if the member is not registered.
        """
        str_discord_user_id = str(discord_user_id)
        normalized_username = _normalize_discord_username(discord_username)

        async with AsyncSessionLocal() as session:
            row = await RosterRepository.get_by_discord_user_id(session, str_discord_user_id)
            if row is not None:
                if row.discord_username != normalized_username:
                    conflict = (
                        await RosterRepository.get_by_discord_username(session, normalized_username)
                        if normalized_username is not None
                        else None
                    )
                    if conflict is not None and conflict.id != row.id:
                        logger.warning(
                            f"Skipping username refresh for id={row.id}: "
                            f"{normalized_username!r} is already taken"
                        )
                    else:
                        row.discord_username = normalized_username
                        row.updated_at = datetime.now(UTC)
                        await session.commit()
                        await _invalidate_caches()
                return _to_person(row)

            if normalized_username is not None:
                row = await RosterRepository.get_by_discord_username(session, normalized_username)
                if row is not None and row.discord_user_id is None:
                    row.discord_user_id = str_discord_user_id
                    row.updated_at = datetime.now(UTC)
                    await session.commit()
                    await _invalidate_caches()
                    return _to_person(row)

            return None

    @staticmethod
    def get_options() -> dict[str, list[str]]:
        """Return the valid class years and living locations for roster forms."""
        return {
            "years": [year.value for year in ClassYear],
            "locations": [location.value for location in CampusLivingLocations],
        }
