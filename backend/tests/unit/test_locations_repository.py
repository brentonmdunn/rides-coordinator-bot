"""Unit tests for LocationsRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.repositories.locations_repository import LocationsRepository

_NOT_SET = object()


def _make_session(rows=None, first=_NOT_SET, scalars_first=_NOT_SET):
    """Build a minimal fake AsyncSession that returns controlled query results."""
    session = AsyncMock()
    result = MagicMock()

    if rows is not None:
        result.all.return_value = rows
    if first is not _NOT_SET:
        result.first.return_value = first
    if scalars_first is not _NOT_SET:
        result.scalars.return_value.first.return_value = scalars_first

    result.scalars.return_value.all.return_value = rows or []
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.mark.asyncio
async def test_get_location_check_discord_returns_rows():
    rows = [("Alice", "Revelle")]
    session = _make_session(rows=rows)

    result = await LocationsRepository.get_location_check_discord(session, "alice")

    assert result == rows


@pytest.mark.asyncio
async def test_get_location_check_name_and_discord_returns_rows():
    rows = [("Bob", "Warren")]
    session = _make_session(rows=rows)

    result = await LocationsRepository.get_location_check_name_and_discord(session, "bob")

    assert result == rows


@pytest.mark.asyncio
async def test_get_discord_username_returns_value():
    session = _make_session(scalars_first="alice_discord")

    result = await LocationsRepository.get_discord_username(session, "Alice")

    assert result == "alice_discord"


@pytest.mark.asyncio
async def test_get_discord_username_returns_none():
    session = _make_session(scalars_first=None)  # uses sentinel, sets to None

    result = await LocationsRepository.get_discord_username(session, "Unknown")

    assert result is None


@pytest.mark.asyncio
async def test_get_name_returns_value():
    session = _make_session(scalars_first="Alice Smith")

    result = await LocationsRepository.get_name(session, "alice")

    assert result == "Alice Smith"


@pytest.mark.asyncio
async def test_get_names_for_usernames_empty_set():
    session = AsyncMock()
    result = await LocationsRepository.get_names_for_usernames(session, set())
    assert result == {}
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_names_for_usernames_maps_correctly():
    rows = [("Alice", "Alice Smith"), ("bob", "Bob Jones")]
    session = _make_session(rows=rows)
    # Override the .all() path used in get_names_for_usernames
    result_obj = MagicMock()
    result_obj.all.return_value = rows
    session.execute = AsyncMock(return_value=result_obj)

    mapping = await LocationsRepository.get_names_for_usernames(session, {"Alice", "bob"})

    assert mapping["Alice"] == "Alice Smith"
    assert mapping["bob"] == "Bob Jones"


@pytest.mark.asyncio
async def test_get_name_location_returns_tuple():
    session = AsyncMock()
    result_obj = MagicMock()
    fake_row = MagicMock()
    fake_row.__getitem__ = MagicMock(side_effect=lambda i: ("Alice", "Revelle")[i])
    result_obj.first.return_value = fake_row
    session.execute = AsyncMock(return_value=result_obj)

    result = await LocationsRepository.get_name_location(session, "alice")

    assert result == ("Alice", "Revelle")


@pytest.mark.asyncio
async def test_get_name_location_returns_none():
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.first.return_value = None
    session.execute = AsyncMock(return_value=result_obj)

    result = await LocationsRepository.get_name_location(session, "nobody")

    assert result is None


@pytest.mark.asyncio
async def test_get_all_discord_usernames_returns_pairs():
    rows = [("alice", "Alice"), ("bob", "Bob")]
    session = AsyncMock()
    result_obj = MagicMock()
    result_obj.all.return_value = rows
    session.execute = AsyncMock(return_value=result_obj)

    result = await LocationsRepository.get_all_discord_usernames(session)

    assert ("alice", "Alice") in result
    assert ("bob", "Bob") in result


@pytest.mark.asyncio
async def test_sync_locations_deletes_and_adds():
    session = AsyncMock()
    from bot.core.models import Locations as LocationsModel

    loc = LocationsModel()
    await LocationsRepository.sync_locations(session, [loc])

    session.execute.assert_called_once()
    session.add_all.assert_called_once_with([loc])
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_locations_empty_list():
    session = AsyncMock()
    await LocationsRepository.sync_locations(session, [])

    session.execute.assert_called_once()
    session.add_all.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_non_discord_pickups_exception_returns_empty():
    """DB exception should be swallowed and return an empty list."""
    session = AsyncMock()
    session.execute.side_effect = RuntimeError("db error")

    from bot.core.enums import JobName

    result = await LocationsRepository.get_non_discord_pickups(session, JobName.FRIDAY)

    assert result == []
