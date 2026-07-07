"""Unit tests for PickupLocationsService CRUD + caching against an in-memory DB."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.core.base import Base
from bot.core.models import GlobalSetting, LivingLocationPickup, PickupLocation
from bot.services.pickup_locations_service import PickupLocationsService


@pytest_asyncio.fixture
async def session_local():
    """In-memory SQLite session factory with all tables created and cache reset."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    PickupLocationsService.invalidate_cache()
    with patch("bot.services.pickup_locations_service.AsyncSessionLocal", factory):
        yield factory
    PickupLocationsService.invalidate_cache()
    await engine.dispose()


async def _seed_minimal(factory):
    """Insert two locations, one mapping, and the adjustment setting."""
    async with factory() as session:
        session.add(
            PickupLocation(id=1, name="Alpha", latitude=32.88, longitude=-117.24, is_seeded=True)
        )
        session.add(
            PickupLocation(id=2, name="Beta", latitude=32.87, longitude=-117.23, is_seeded=True)
        )
        session.add(LivingLocationPickup(living_location="Muir", pickup_location_id=1))
        session.add(GlobalSetting(key="ride_grouping_pickup_adjustment", value="3"))
        await session.commit()


@pytest.mark.asyncio
async def test_get_all_returns_full_payload(session_local):
    await _seed_minimal(session_local)
    payload = await PickupLocationsService.get_all()

    assert {loc["name"] for loc in payload["locations"]} == {"Alpha", "Beta"}
    assert payload["edges"] == []
    assert payload["living_mappings"] == [{"living_location": "Muir", "pickup_location_id": 1}]
    assert payload["pickup_adjustment"] == 3
    # No edges and no start/end minutes: everything is unreachable
    assert set(payload["unreachable"]) == {"Alpha", "Beta"}


@pytest.mark.asyncio
async def test_create_location_and_duplicate_rejected(session_local):
    created = await PickupLocationsService.create_location(
        name="Gamma", latitude=32.9, longitude=-117.25, minutes_from_start=5
    )
    assert created.id is not None
    assert created.minutes_from_start == 5

    with pytest.raises(ValueError, match="already exists"):
        await PickupLocationsService.create_location(name="Gamma", latitude=1.0, longitude=2.0)


@pytest.mark.asyncio
async def test_update_location_and_rename_conflict(session_local):
    await _seed_minimal(session_local)
    updated = await PickupLocationsService.update_location(2, name="Beta 2", latitude=33.0)
    assert updated is not None
    assert updated.name == "Beta 2"
    assert updated.latitude == 33.0

    assert await PickupLocationsService.update_location(999, name="X") is None

    with pytest.raises(ValueError, match="already exists"):
        await PickupLocationsService.update_location(2, name="Alpha")


@pytest.mark.asyncio
async def test_soft_delete_blocked_by_mapping_then_allowed(session_local):
    await _seed_minimal(session_local)

    with pytest.raises(ValueError, match="Muir"):
        await PickupLocationsService.soft_delete_location(1)

    # Remap Muir to Beta, then deletion succeeds
    await PickupLocationsService.set_living_mapping("Muir", 2)
    assert await PickupLocationsService.soft_delete_location(1) is True

    payload = await PickupLocationsService.get_all()
    alpha = next(loc for loc in payload["locations"] if loc["name"] == "Alpha")
    assert alpha["is_active"] is False

    assert await PickupLocationsService.soft_delete_location(999) is False


@pytest.mark.asyncio
async def test_upsert_edge_creates_updates_and_validates(session_local):
    await _seed_minimal(session_local)

    edge = await PickupLocationsService.upsert_edge(2, 1, minutes=4)
    # Pair normalized so a < b
    assert (edge.location_a_id, edge.location_b_id) == (1, 2)
    assert edge.minutes == 4

    # Upsert same pair updates in place
    edge2 = await PickupLocationsService.upsert_edge(1, 2, minutes=7)
    assert edge2.id == edge.id
    assert edge2.minutes == 7

    with pytest.raises(ValueError, match="different locations"):
        await PickupLocationsService.upsert_edge(1, 1, minutes=2)

    with pytest.raises(ValueError, match="Unknown or inactive"):
        await PickupLocationsService.upsert_edge(1, 999, minutes=2)


@pytest.mark.asyncio
async def test_edge_makes_locations_connected_via_start(session_local):
    await _seed_minimal(session_local)
    await PickupLocationsService.upsert_edge(1, 2, minutes=4)
    await PickupLocationsService.update_location(1, minutes_from_start=10, minutes_to_end=20)

    ctx = await PickupLocationsService.get_routing_context()
    assert ctx.lookup_time("Alpha", "Beta") == 4
    assert ctx.unreachable_names() == []


@pytest.mark.asyncio
async def test_delete_edge(session_local):
    await _seed_minimal(session_local)
    edge = await PickupLocationsService.upsert_edge(1, 2, minutes=4)

    assert await PickupLocationsService.delete_edge(edge.id) is True
    assert await PickupLocationsService.delete_edge(edge.id) is False


@pytest.mark.asyncio
async def test_set_living_mapping_validation(session_local):
    await _seed_minimal(session_local)

    with pytest.raises(ValueError, match="Unknown living location"):
        await PickupLocationsService.set_living_mapping("Atlantis", 1)

    with pytest.raises(ValueError, match="Unknown or inactive"):
        await PickupLocationsService.set_living_mapping("Muir", 999)

    result = await PickupLocationsService.set_living_mapping("Warren", 2)
    assert result == {"living_location": "Warren", "pickup_location_id": 2}


@pytest.mark.asyncio
async def test_set_pickup_adjustment(session_local):
    await _seed_minimal(session_local)
    assert await PickupLocationsService.set_pickup_adjustment(5) == 5

    payload = await PickupLocationsService.get_all()
    assert payload["pickup_adjustment"] == 5

    with pytest.raises(ValueError, match=">= 0"):
        await PickupLocationsService.set_pickup_adjustment(-1)


@pytest.mark.asyncio
async def test_cache_invalidated_on_mutation(session_local):
    await _seed_minimal(session_local)
    first = await PickupLocationsService.get_routing_context()
    # Cached: same object identity on second read
    assert await PickupLocationsService.get_routing_context() is first

    await PickupLocationsService.create_location(name="Gamma", latitude=1.0, longitude=2.0)
    second = await PickupLocationsService.get_routing_context()
    assert second is not first
    assert "Gamma" in [loc.name for loc in second.locations]


@pytest.mark.asyncio
async def test_inactive_location_excluded_from_graph_and_fuzzy(session_local):
    await _seed_minimal(session_local)
    await PickupLocationsService.upsert_edge(1, 2, minutes=4)
    await PickupLocationsService.set_living_mapping("Muir", 2)
    await PickupLocationsService.soft_delete_location(1)

    ctx = await PickupLocationsService.get_routing_context()
    assert "Alpha" not in ctx.active_names
    assert ctx.fuzzy_match("Alpha") is None
    with pytest.raises(ValueError, match="No path found"):
        ctx.lookup_time("Beta", "Alpha")
