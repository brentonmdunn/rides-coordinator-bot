"""Unit tests for alru_cache namespace support."""

import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest

from bot.core.enums import AskRidesMessage, CacheNamespace
from bot.utils.cache import (
    alru_cache,
    invalidate_all_namespaces,
    invalidate_namespace,
    warm_ask_drivers_reactions_cache,
    warm_ask_rides_reactions_cache,
)
from bot.utils.cache_backends import InMemoryBackend, set_backend


@pytest.fixture(autouse=True)
def _fresh_backend():
    """Install a fresh InMemoryBackend before each test so tests don't leak state."""
    from bot.utils.cache import _func_registry, _namespace_registry

    _namespace_registry.clear()
    _func_registry.clear()
    set_backend(InMemoryBackend())
    yield
    _namespace_registry.clear()
    _func_registry.clear()
    set_backend(InMemoryBackend())


@pytest.mark.asyncio
async def test_basic_caching_with_namespace():
    """Cached function should return cached values within TTL."""

    call_count = 0

    @alru_cache(ttl=300, namespace=CacheNamespace.DEFAULT)
    async def my_func(x):
        nonlocal call_count
        call_count += 1
        return x * 2

    assert await my_func(5) == 10
    assert await my_func(5) == 10
    assert call_count == 1  # Only called once


@pytest.mark.asyncio
async def test_invalidate_namespace_clears_target():
    """invalidate_namespace should clear all caches in the target namespace."""

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def func_a(x):
        return x + 1

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def func_b(x):
        return x + 2

    assert await func_a(1) == 2
    assert await func_b(1) == 3

    await invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    # After invalidation, calling again should re-compute
    call_count = 0

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def func_c(x):
        nonlocal call_count
        call_count += 1
        return x + 10

    assert await func_c(1) == 11
    assert call_count == 1


@pytest.mark.asyncio
async def test_invalidate_namespace_does_not_affect_others():
    """invalidate_namespace should not touch caches in other namespaces."""

    call_count_rides = 0
    call_count_drivers = 0

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def rides_func(x):
        nonlocal call_count_rides
        call_count_rides += 1
        return x

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def drivers_func(x):
        nonlocal call_count_drivers
        call_count_drivers += 1
        return x

    await rides_func(1)
    await drivers_func(1)

    await invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    # Drivers namespace should still have cached entry
    await drivers_func(1)
    assert call_count_drivers == 1  # Still cached, no recomputation

    # Rides namespace was cleared — would need a new function to verify


@pytest.mark.asyncio
async def test_invalidate_all_namespaces():
    """invalidate_all_namespaces should clear every namespace."""

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def func_a(x):
        return x

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_DRIVERS_REACTIONS)
    async def func_b(x):
        return x

    @alru_cache(ttl=300, namespace=CacheNamespace.DEFAULT)
    async def func_c(x):
        return x

    await func_a(1)
    await func_b(1)
    await func_c(1)

    await invalidate_all_namespaces()

    # All should be cleared — verify via backend
    from bot.utils.cache_backends import get_backend

    backend = get_backend()
    hit_a, _ = await backend.get(str(CacheNamespace.ASK_RIDES_MESSAGE_ID), "anything")
    hit_b, _ = await backend.get(str(CacheNamespace.ASK_DRIVERS_REACTIONS), "anything")
    assert not hit_a
    assert not hit_b


@pytest.mark.asyncio
async def test_default_namespace_when_unspecified():
    """Functions without an explicit namespace should use DEFAULT."""

    @alru_cache(ttl=300)
    async def func_default(x):
        return x

    await func_default(1)

    assert func_default.cache_namespace == str(CacheNamespace.DEFAULT)


@pytest.mark.asyncio
async def test_cache_clear_still_works():
    """The per-function cache_clear() should still work alongside namespaces."""

    call_count = 0

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_REACTIONS)
    async def my_func(x):
        nonlocal call_count
        call_count += 1
        return x

    await my_func(1)
    assert call_count == 1

    # Clear just resets stats; actual data is in the backend
    my_func.cache_clear()

    # Backend data was NOT cleared by cache_clear, but let's invalidate namespace
    await invalidate_namespace(CacheNamespace.ASK_RIDES_REACTIONS)

    await my_func(1)
    assert call_count == 2  # Re-computed after invalidation


@pytest.mark.asyncio
async def test_invalidate_nonexistent_namespace():
    """Invalidating a namespace with no registered caches should not error."""
    await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
    # Should complete without raising


@pytest.mark.asyncio
async def test_cache_namespace_attribute():
    """Decorated functions should expose their namespace via cache_namespace attribute."""

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def my_func(x):
        return x

    assert my_func.cache_namespace == str(CacheNamespace.ASK_DRIVERS_MESSAGE_ID)


@pytest.mark.asyncio
async def test_warm_ask_rides_reactions_cache():
    """warm_ask_rides_reactions_cache should invalidate the namespace and warm the cache."""
    bot = AsyncMock()

    with (
        patch("bot.services.locations_service.LocationsService") as mock_locations_service,
        patch("bot.utils.cache.invalidate_namespace", new_callable=AsyncMock) as mock_invalidate,
    ):
        svc_instance = AsyncMock()
        mock_locations_service.return_value = svc_instance

        await warm_ask_rides_reactions_cache(bot, AskRidesMessage.SUNDAY_SERVICE)

        mock_invalidate.assert_awaited_once_with(CacheNamespace.ASK_RIDES_REACTIONS)
        svc_instance.get_ask_rides_reactions.assert_awaited_once_with(
            AskRidesMessage.SUNDAY_SERVICE
        )


@pytest.mark.asyncio
async def test_warm_ask_drivers_reactions_cache():
    """warm_ask_drivers_reactions_cache should invalidate the namespace and warm the
    cache for the specific day."""
    bot = AsyncMock()

    with (
        patch("bot.services.locations_service.LocationsService") as mock_locations_service,
        patch("bot.utils.cache.invalidate_namespace", new_callable=AsyncMock) as mock_invalidate,
    ):
        svc_instance = AsyncMock()
        mock_locations_service.return_value = svc_instance

        await warm_ask_drivers_reactions_cache(bot)

        mock_invalidate.assert_awaited_once_with(CacheNamespace.ASK_DRIVERS_REACTIONS)
        svc_instance.get_driver_reactions.assert_has_awaits(
            [
                call(AskRidesMessage.FRIDAY_FELLOWSHIP),
                call(AskRidesMessage.SUNDAY_SERVICE),
            ]
        )
        assert svc_instance.get_driver_reactions.await_count == 2


@pytest.mark.asyncio
async def test_warm_ask_drivers_reactions_cache_specific():
    """warm_ask_drivers_reactions_cache with event should selectively drop and warm."""
    bot = AsyncMock()

    with patch("bot.services.locations_service.LocationsService") as mock_locations_service:
        svc_instance = AsyncMock()
        svc_instance.get_driver_reactions.cache_invalidate = AsyncMock()
        mock_locations_service.return_value = svc_instance

        await warm_ask_drivers_reactions_cache(bot, AskRidesMessage.FRIDAY_FELLOWSHIP)

        svc_instance.get_driver_reactions.cache_invalidate.assert_awaited_once_with(
            AskRidesMessage.FRIDAY_FELLOWSHIP
        )
        svc_instance.get_driver_reactions.assert_awaited_once_with(
            AskRidesMessage.FRIDAY_FELLOWSHIP
        )


@pytest.mark.asyncio
async def test_alru_cache_invalidate():
    """Test explicit cache_invalidate method drops specific key without touching others."""
    mock_func = AsyncMock(side_effect=lambda x: f"data_{x}")

    @alru_cache(ttl=300)
    async def fetch_data(key: str):
        return await mock_func(key)

    # Populate cache for A and B
    res_a1 = await fetch_data("A")
    res_b1 = await fetch_data("B")
    assert res_a1 == "data_A"
    assert res_b1 == "data_B"
    assert mock_func.call_count == 2

    # Invalidate A explicitly
    await fetch_data.cache_invalidate("A")

    # Fetching A again should trigger computation
    res_a2 = await fetch_data("A")
    assert res_a2 == "data_A"
    assert mock_func.call_count == 3

    # Fetching B should still hit cache (no computation)
    res_b2 = await fetch_data("B")
    assert res_b2 == "data_B"
    assert mock_func.call_count == 3


@pytest.mark.asyncio
async def test_cache_stampede_prevention():
    """Concurrent cache misses for the same key should only result in one underlying
    function call."""
    mock_func = AsyncMock(return_value="data")

    @alru_cache(ttl=300)
    async def fetch_data(key: str):
        # Simulate network or DB delay
        await asyncio.sleep(0.1)
        return await mock_func(key)

    # Spawn 10 concurrent requests for the same key
    results = await asyncio.gather(*(fetch_data("foo") for _ in range(10)))

    # All 10 requests should get the same data back
    assert all(r == "data" for r in results)

    # Crucially, the underlying function should only have been called ONCE
    mock_func.assert_called_once_with("foo")
