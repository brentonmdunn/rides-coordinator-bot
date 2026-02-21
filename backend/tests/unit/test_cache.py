"""Unit tests for alru_cache namespace support."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from bot.core.enums import AskRidesMessage, CacheNamespace
from bot.utils.cache import (
    _namespace_registry,
    alru_cache,
    invalidate_all_namespaces,
    invalidate_namespace,
    warm_ask_drivers_reactions_cache,
    warm_ask_rides_reactions_cache,
)


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the namespace registry before and after each test."""
    _namespace_registry.clear()
    yield
    _namespace_registry.clear()


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

    await func_a(1)
    await func_b(1)

    # Both should have cached entries
    caches = _namespace_registry[CacheNamespace.ASK_RIDES_MESSAGE_ID]
    assert all(len(c) > 0 for c in caches)

    invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    # All caches in that namespace should be empty
    assert all(len(c) == 0 for c in caches)


@pytest.mark.asyncio
async def test_invalidate_namespace_does_not_affect_others():
    """invalidate_namespace should not touch caches in other namespaces."""

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def rides_func(x):
        return x

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def drivers_func(x):
        return x

    await rides_func(1)
    await drivers_func(1)

    invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    # Rides namespace should be cleared
    assert all(len(c) == 0 for c in _namespace_registry[CacheNamespace.ASK_RIDES_MESSAGE_ID])

    # Drivers namespace should still have entries
    drivers_caches = _namespace_registry[CacheNamespace.ASK_DRIVERS_MESSAGE_ID]
    assert any(len(c) > 0 for c in drivers_caches)


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

    invalidate_all_namespaces()

    for caches in _namespace_registry.values():
        assert all(len(c) == 0 for c in caches)


@pytest.mark.asyncio
async def test_default_namespace_when_unspecified():
    """Functions without an explicit namespace should use DEFAULT."""

    @alru_cache(ttl=300)
    async def func_default(x):
        return x

    await func_default(1)

    assert CacheNamespace.DEFAULT in _namespace_registry
    assert any(len(c) > 0 for c in _namespace_registry[CacheNamespace.DEFAULT])


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

    my_func.cache_clear()

    await my_func(1)
    assert call_count == 2  # Re-computed after clear


@pytest.mark.asyncio
async def test_invalidate_nonexistent_namespace():
    """Invalidating a namespace with no registered caches should not error."""
    invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
    # Should complete without raising


@pytest.mark.asyncio
async def test_cache_namespace_attribute():
    """Decorated functions should expose their namespace via cache_namespace attribute."""

    @alru_cache(ttl=300, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def my_func(x):
        return x

    assert my_func.cache_namespace == CacheNamespace.ASK_DRIVERS_MESSAGE_ID


@pytest.mark.asyncio
async def test_warm_ask_rides_reactions_cache():
    """warm_ask_rides_reactions_cache should invalidate the namespace and warm the cache."""
    bot = AsyncMock()

    with (
        patch("bot.services.locations_service.LocationsService") as mock_locations_service,
        patch("bot.utils.cache.invalidate_namespace") as mock_invalidate,
    ):
        svc_instance = AsyncMock()
        mock_locations_service.return_value = svc_instance

        await warm_ask_rides_reactions_cache(bot, AskRidesMessage.SUNDAY_SERVICE)

        mock_invalidate.assert_called_once_with(CacheNamespace.ASK_RIDES_REACTIONS)
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
        patch("bot.utils.cache.invalidate_namespace") as mock_invalidate,
    ):
        svc_instance = AsyncMock()
        mock_locations_service.return_value = svc_instance

        await warm_ask_drivers_reactions_cache(bot, AskRidesMessage.FRIDAY_FELLOWSHIP)

        mock_invalidate.assert_called_once_with(CacheNamespace.ASK_DRIVERS_REACTIONS)
        svc_instance.get_driver_reactions.assert_awaited_once_with("Friday")


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
