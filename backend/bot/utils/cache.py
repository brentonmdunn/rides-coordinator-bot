"""Simple async LRU cache with TTL and namespace support."""

import functools
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

from bot.core.enums import CacheNamespace
from bot.core.logger import logger

T = TypeVar("T")

# Global registry: namespace -> list of cache dicts belonging to that namespace
_namespace_registry: dict[str, list[OrderedDict]] = {}


def alru_cache(
    maxsize: int = 128,
    ttl: int | float | Callable[[], int | float] | None = None,
    ignore_self: bool = False,
    namespace: CacheNamespace = CacheNamespace.DEFAULT,
) -> Callable:
    """
    Async Least Recently Used (LRU) cache decorator with Time To Live (TTL).

    Args:
        maxsize: Maximum number of items to keep in the cache.
        ttl: Time to live in seconds. Can be:
             - int/float: Fixed TTL in seconds
             - Callable: Function that returns TTL in seconds (evaluated at cache time)
             - None: Items never expire by time
        ignore_self: If True, ignores the first argument (self/cls) in cache key.
                     Useful for caching instance methods globally across instances.
        namespace: Cache namespace for grouped invalidation.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache: OrderedDict = OrderedDict()

        # Register this cache in the namespace registry
        ns_key = str(namespace)
        if ns_key not in _namespace_registry:
            _namespace_registry[ns_key] = []
        _namespace_registry[ns_key].append(cache)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            key_args = args[1:] if ignore_self and args else args
            key = (key_args, tuple(sorted(kwargs.items())))

            # Check if key is in cache
            if key in cache:
                result, timestamp, cached_ttl = cache[key]

                # Check if expired
                if cached_ttl is not None and time.time() - timestamp > cached_ttl:
                    del cache[key]
                else:
                    # Move to end (most recently used)
                    cache.move_to_end(key)
                    return result

            # Compute result
            result = await func(*args, **kwargs)

            # Calculate TTL (support dynamic TTL via callable)
            current_ttl = ttl() if callable(ttl) else ttl

            # Add to cache with computed TTL
            cache[key] = (result, time.time(), current_ttl)
            cache.move_to_end(key)

            # Enforce maxsize
            if len(cache) > maxsize:
                cache.popitem(last=False)

            return result

        def cache_clear():
            """Clear all cached entries for this function."""
            cache.clear()
            logger.info(f"Cache cleared for {func.__name__}")

        wrapper.cache_clear = cache_clear
        wrapper.cache_namespace = ns_key
        return wrapper

    return decorator


def invalidate_namespace(namespace: CacheNamespace) -> None:
    """Clear all caches registered under a namespace.

    Args:
        namespace: The namespace to invalidate.
    """
    ns_key = str(namespace)
    caches = _namespace_registry.get(ns_key, [])
    total_cleared = 0
    for cache in caches:
        total_cleared += len(cache)
        cache.clear()
    if total_cleared > 0:
        logger.info(f"Invalidated namespace '{ns_key}': cleared {total_cleared} entries")


def invalidate_all_namespaces() -> None:
    """Clear all caches across every namespace."""
    total_cleared = 0
    for _ns_key, caches in _namespace_registry.items():
        for cache in caches:
            total_cleared += len(cache)
            cache.clear()
    if total_cleared > 0:
        logger.info(f"Invalidated all namespaces: cleared {total_cleared} entries")


# ============================================================================
# Cache Warming Helpers
# ============================================================================


async def warm_ask_rides_message_cache(bot, channel_id=None) -> None:
    """Invalidate and re-populate the ask-rides message ID cache.

    Call this after sending new ask-rides messages.

    Args:
        bot: The Discord bot instance.
        channel_id: Optional channel ID override (defaults to RIDES_ANNOUNCEMENTS).
    """
    from bot.core.enums import AskRidesMessage, ChannelIds
    from bot.services.locations_service import LocationsService

    if channel_id is None:
        channel_id = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS

    invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
    invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    locations_svc = LocationsService(bot)
    for msg_type in AskRidesMessage:
        await locations_svc._find_correct_message(msg_type, channel_id)
    logger.info("Warmed ask rides message ID cache")


async def warm_ask_drivers_message_cache(bot, event) -> None:
    """Invalidate and re-populate the ask-drivers message ID cache for a specific event.

    Call this after sending a new ask-drivers message.

    Args:
        bot: The Discord bot instance.
        event: The AskRidesMessage enum value for the day that was sent.
    """
    from bot.services.locations_service import LocationsService

    invalidate_namespace(CacheNamespace.ASK_DRIVERS_MESSAGE_ID)

    locations_svc = LocationsService(bot)
    await locations_svc._find_driver_message(event)
    logger.info(f"Warmed ask drivers message ID cache for {event}")
