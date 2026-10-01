"""Tests for the one-off shane reaction backfill script (item C)."""

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import scripts.backfill_shane_reaction as backfill
from shared.core.models import Base, RideReactionEvent


@pytest_asyncio.fixture
async def session_factory(monkeypatch):
    """In-memory DB shared across connections, patched in for AsyncSessionLocal."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(backfill, "AsyncSessionLocal", factory)
    yield factory
    await engine.dispose()


async def _row_count(factory) -> int:
    async with factory() as session:
        result = await session.execute(select(func.count()).select_from(RideReactionEvent))
        return result.scalar_one()


@pytest.mark.asyncio
async def test_dry_run_inserts_nothing(session_factory):
    await backfill.backfill(dry_run=True)
    assert await _row_count(session_factory) == 0


@pytest.mark.asyncio
async def test_apply_inserts_one_row(session_factory):
    await backfill.backfill(dry_run=False)
    assert await _row_count(session_factory) == 1

    async with session_factory() as session:
        row = (await session.execute(select(RideReactionEvent))).scalar_one()
    assert row.discord_username == "shane9910199"
    assert row.emoji == "🍔"
    assert row.action == "add"
    assert row.ride_type == "sunday"
    assert row.display_name is None


@pytest.mark.asyncio
async def test_running_twice_inserts_exactly_one_row(session_factory):
    await backfill.backfill(dry_run=False)
    await backfill.backfill(dry_run=False)
    assert await _row_count(session_factory) == 1
