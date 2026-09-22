"""Unit tests for PickupInfoRepository CRUD against an in-memory DB."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ridebot.repositories.pickup_info_repository import PickupInfoRepository
from shared.core.base import Base
from shared.core.models import Locations


@pytest_asyncio.fixture
async def session_local():
    """In-memory SQLite session factory with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _seed(factory, *entries: Locations):
    async with factory() as session:
        session.add_all(entries)
        await session.commit()


@pytest.mark.asyncio
async def test_get_all_orders_by_lowercase_name(session_local):
    await _seed(
        session_local,
        Locations(name="charlie"),
        Locations(name="Alice"),
        Locations(name="bob"),
    )
    async with session_local() as session:
        rows = await PickupInfoRepository.get_all(session)
    assert [row.name for row in rows] == ["Alice", "bob", "charlie"]


@pytest.mark.asyncio
async def test_get_by_id(session_local):
    await _seed(session_local, Locations(id=1, name="Alice"))
    async with session_local() as session:
        assert (await PickupInfoRepository.get_by_id(session, 1)).name == "Alice"
        assert await PickupInfoRepository.get_by_id(session, 999) is None


@pytest.mark.asyncio
async def test_get_by_ids(session_local):
    await _seed(
        session_local,
        Locations(id=1, name="Alice"),
        Locations(id=2, name="Bob"),
        Locations(id=3, name="Carl"),
    )
    async with session_local() as session:
        rows = await PickupInfoRepository.get_by_ids(session, [1, 3, 999])
    assert {row.id for row in rows} == {1, 3}
    async with session_local() as session:
        assert await PickupInfoRepository.get_by_ids(session, []) == []


@pytest.mark.asyncio
async def test_get_by_discord_user_id(session_local):
    await _seed(session_local, Locations(name="Alice", discord_user_id="123"))
    async with session_local() as session:
        row = await PickupInfoRepository.get_by_discord_user_id(session, "123")
        assert row is not None
        assert row.name == "Alice"
        assert await PickupInfoRepository.get_by_discord_user_id(session, "999") is None


@pytest.mark.asyncio
async def test_get_by_discord_username_case_insensitive(session_local):
    await _seed(session_local, Locations(name="Alice", discord_username="alicew"))
    async with session_local() as session:
        row = await PickupInfoRepository.get_by_discord_username(session, "AliceW")
        assert row is not None
        assert row.name == "Alice"
        assert await PickupInfoRepository.get_by_discord_username(session, "nobody") is None


@pytest.mark.asyncio
async def test_create_flushes_without_committing(session_local):
    now = datetime.now(UTC)
    async with session_local() as session:
        row = await PickupInfoRepository.create(
            session,
            name="Alice",
            discord_username="alicew",
            discord_user_id="123",
            year="1st",
            location="Muir",
            updated_at=now,
        )
        assert row.id is not None
        assert row.phone is None
        await session.rollback()

    async with session_local() as session:
        rows = await PickupInfoRepository.get_all(session)
    assert rows == []


@pytest.mark.asyncio
async def test_create_with_phone(session_local):
    now = datetime.now(UTC)
    async with session_local() as session:
        row = await PickupInfoRepository.create(
            session,
            name="Alice",
            discord_username="alicew",
            discord_user_id="123",
            year="1st",
            location="Muir",
            phone="8585551234",
            updated_at=now,
        )
        assert row.phone == "8585551234"


@pytest.mark.asyncio
async def test_delete_by_ids(session_local):
    await _seed(
        session_local,
        Locations(id=1, name="Alice"),
        Locations(id=2, name="Bob"),
    )
    async with session_local() as session:
        count = await PickupInfoRepository.delete_by_ids(session, [1, 999])
        await session.commit()
    assert count == 1

    async with session_local() as session:
        rows = await PickupInfoRepository.get_all(session)
    assert [row.id for row in rows] == [2]


@pytest.mark.asyncio
async def test_delete_by_ids_empty_list(session_local):
    async with session_local() as session:
        assert await PickupInfoRepository.delete_by_ids(session, []) == 0
