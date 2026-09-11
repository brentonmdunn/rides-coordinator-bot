"""Unit tests for RosterService validation, CRUD, register/find, and cache invalidation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ridebot.services.roster_service import PersonInput, RosterService
from ridebot.utils.custom_exceptions import (
    RosterConflictError,
    RosterNotFoundError,
    RosterValidationError,
)
from shared.core.base import Base
from shared.core.models import Locations


@pytest_asyncio.fixture
async def session_local():
    """In-memory SQLite session factory with all tables created and cache invalidation mocked."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("ridebot.services.roster_service.AsyncSessionLocal", factory),
        patch(
            "ridebot.services.roster_service.invalidate_namespace", new_callable=AsyncMock
        ) as mock_invalidate,
    ):
        yield factory, mock_invalidate
    await engine.dispose()


async def _seed(factory, *entries: Locations):
    async with factory() as session:
        session.add_all(entries)
        await session.commit()


# --- list / get ----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_people_orders_by_name(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(name="Bob"), Locations(name="Alice"))
    people = await RosterService.list_people()
    assert [p.name for p in people] == ["Alice", "Bob"]


@pytest.mark.asyncio
async def test_get_person_not_found(session_local):
    with pytest.raises(RosterNotFoundError):
        await RosterService.get_person(999)


# --- create validation -----------------------------------------------------


@pytest.mark.asyncio
async def test_create_person_success_invalidates_cache(session_local):
    _, mock_invalidate = session_local
    person = await RosterService.create_person(
        PersonInput(name="Alice", discord_username="@AliceW", year="1st", location="muir")
    )
    assert person.name == "Alice"
    assert person.discord_username == "alicew"
    assert person.year == "1st"
    assert person.location == "Muir"
    assert person.updated_at is not None
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_create_person_empty_name_invalid(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="   "))


@pytest.mark.asyncio
async def test_create_person_name_too_long_invalid(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="a" * 101))


@pytest.mark.asyncio
async def test_create_person_username_empty_becomes_none(session_local):
    person = await RosterService.create_person(PersonInput(name="Alice", discord_username=""))
    assert person.discord_username is None


@pytest.mark.asyncio
async def test_create_person_username_too_long_invalid(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="Alice", discord_username="a" * 33))


@pytest.mark.asyncio
async def test_create_person_username_bad_chars_invalid(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="Alice", discord_username="al!ce"))


@pytest.mark.asyncio
async def test_create_person_invalid_year(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="Alice", year="7th"))


@pytest.mark.asyncio
async def test_create_person_invalid_location(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.create_person(PersonInput(name="Alice", location="Mars"))


@pytest.mark.asyncio
async def test_create_person_duplicate_username_conflict(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(name="Bob", discord_username="alicew"))
    with pytest.raises(RosterConflictError):
        await RosterService.create_person(PersonInput(name="Alice", discord_username="AliceW"))


# --- update ------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_person_not_found(session_local):
    with pytest.raises(RosterNotFoundError):
        await RosterService.update_person(999, {"name": "Alice"})


@pytest.mark.asyncio
async def test_update_person_unknown_field(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(id=1, name="Alice"))
    with pytest.raises(RosterValidationError):
        await RosterService.update_person(1, {"driver": "Yes"})


@pytest.mark.asyncio
async def test_update_person_clears_nullable_field(session_local):
    factory, mock_invalidate = session_local
    await _seed(factory, Locations(id=1, name="Alice", location="Muir"))
    updated = await RosterService.update_person(1, {"location": None})
    assert updated.location is None
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_update_person_name_cannot_be_none(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(id=1, name="Alice"))
    with pytest.raises(RosterValidationError):
        await RosterService.update_person(1, {"name": None})


@pytest.mark.asyncio
async def test_update_person_only_applies_present_keys(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(id=1, name="Alice", year="1st"))
    updated = await RosterService.update_person(1, {"location": "Muir"})
    assert updated.year == "1st"
    assert updated.location == "Muir"


@pytest.mark.asyncio
async def test_update_person_username_conflict(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice"),
        Locations(id=2, name="Bob", discord_username="bobw"),
    )
    with pytest.raises(RosterConflictError):
        await RosterService.update_person(1, {"discord_username": "bobw"})


@pytest.mark.asyncio
async def test_update_person_same_username_no_conflict(session_local):
    factory, _ = session_local
    await _seed(factory, Locations(id=1, name="Alice", discord_username="alicew"))
    updated = await RosterService.update_person(1, {"discord_username": "AliceW"})
    assert updated.discord_username == "alicew"


# --- delete --------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_people_counts_and_ignores_unknown(session_local):
    factory, mock_invalidate = session_local
    await _seed(factory, Locations(id=1, name="Alice"), Locations(id=2, name="Bob"))
    count = await RosterService.delete_people([1, 999])
    assert count == 1
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_delete_people_empty_does_not_invalidate(session_local):
    _, mock_invalidate = session_local
    count = await RosterService.delete_people([999])
    assert count == 0
    mock_invalidate.assert_not_awaited()


# --- register_from_discord -----------------------------------------------


@pytest.mark.asyncio
async def test_register_from_discord_requires_year_and_location(session_local):
    with pytest.raises(RosterValidationError):
        await RosterService.register_from_discord(
            discord_user_id=1,
            discord_username="alicew",
            name="Alice",
            year=None,
            location="Muir",
        )


@pytest.mark.asyncio
async def test_register_from_discord_creates_new_row(session_local):
    _, mock_invalidate = session_local
    person, created = await RosterService.register_from_discord(
        discord_user_id=42,
        discord_username="AliceW",
        name="Alice",
        year="1st",
        location="muir",
    )
    assert created is True
    assert person.discord_user_id == "42"
    assert person.discord_username == "alicew"
    assert person.location == "Muir"
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_register_from_discord_updates_by_id(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_user_id="42", discord_username="old"),
    )
    person, created = await RosterService.register_from_discord(
        discord_user_id=42,
        discord_username="newname",
        name="Alice Updated",
        year="2nd",
        location="Sixth",
    )
    assert created is False
    assert person.id == 1
    assert person.name == "Alice Updated"
    assert person.discord_username == "newname"
    assert person.year == "2nd"


@pytest.mark.asyncio
async def test_register_from_discord_claims_by_username(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_username="alicew", discord_user_id=None),
    )
    person, created = await RosterService.register_from_discord(
        discord_user_id=42,
        discord_username="AliceW",
        name="Alice",
        year="1st",
        location="Muir",
    )
    assert created is False
    assert person.id == 1
    assert person.discord_user_id == "42"


@pytest.mark.asyncio
async def test_register_from_discord_username_conflict(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_username="alicew", discord_user_id="1"),
    )
    with pytest.raises(RosterConflictError):
        await RosterService.register_from_discord(
            discord_user_id=99,
            discord_username="AliceW",
            name="Someone",
            year="1st",
            location="Muir",
        )


# --- find_member -----------------------------------------------------------


@pytest.mark.asyncio
async def test_find_member_not_registered_returns_none(session_local):
    result = await RosterService.find_member(discord_user_id=1, discord_username="nobody")
    assert result is None


@pytest.mark.asyncio
async def test_find_member_by_id_refreshes_username(session_local):
    factory, mock_invalidate = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_user_id="1", discord_username="old"),
    )
    result = await RosterService.find_member(discord_user_id=1, discord_username="newname")
    assert result is not None
    assert result.discord_username == "newname"
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_find_member_by_id_skips_conflicting_username(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_user_id="1", discord_username="old"),
        Locations(id=2, name="Bob", discord_username="taken"),
    )
    result = await RosterService.find_member(discord_user_id=1, discord_username="taken")
    assert result is not None
    assert result.discord_username == "old"


@pytest.mark.asyncio
async def test_find_member_claims_unlinked_row_by_username(session_local):
    factory, mock_invalidate = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_username="alicew", discord_user_id=None),
    )
    result = await RosterService.find_member(discord_user_id=42, discord_username="AliceW")
    assert result is not None
    assert result.id == 1
    assert result.discord_user_id == "42"
    mock_invalidate.assert_awaited()


@pytest.mark.asyncio
async def test_find_member_username_linked_elsewhere_returns_none(session_local):
    factory, _ = session_local
    await _seed(
        factory,
        Locations(id=1, name="Alice", discord_username="alicew", discord_user_id="1"),
    )
    result = await RosterService.find_member(discord_user_id=99, discord_username="AliceW")
    assert result is None


# --- get_options -------------------------------------------------------


def test_get_options_returns_enum_values():
    options = RosterService.get_options()
    assert "years" in options
    assert "locations" in options
    assert len(options["years"]) > 0
    assert len(options["locations"]) > 0
