"""Simple async LRU cache with TTL and namespace support.

Storage is delegated to a pluggable ``CacheBackend`` (see
``cache_backends.py``).  The default backend is ``InMemoryBackend``; call
``set_backend(RedisBackend(...))`` at startup to switch to Redis.
"""

import asyncio
import functools
import hashlib
import pickle
from collections.abc import Callable
from typing import Any, TypeVar

from bot.core.enums import CacheNamespace
from bot.core.logger import logger
from bot.utils.cache_backends import get_backend

T = TypeVar("T")

# Global registry: namespace -> list of wrapper references (for invalidation)
_namespace_registry: dict[str, list[Callable]] = {}

# Global registry: namespace -> list of (func_name, stats_callable)
_func_registry: dict[str, list[tuple[str, Callable]]] = {}

# Cache TTL constants (in seconds)
ACTIVE_HOURS_REACTION_TTL = 65 * 60  # 65 minutes
OFF_HOURS_REACTION_TTL = 7 * 60 * 60  # 7 hours


def _get_reaction_cache_ttl() -> int:
    """Return dynamic TTL for reaction caches based on time of day.

    Active hours (7 AM - 1 AM PT): 65 minutes
    Off-hours (1 AM - 7 AM PT): 7 hours

    Returns:
        TTL in seconds.
    """
    from bot.utils.time_helpers import is_active_hours

    if is_active_hours():
        return ACTIVE_HOURS_REACTION_TTL
    return OFF_HOURS_REACTION_TTL


def _make_cache_key(*args, **kwargs) -> str:
    """Create a stable, hashable string key from function arguments."""
    raw = pickle.dumps((args, tuple(sorted(kwargs.items()))))
    return hashlib.sha256(raw).hexdigest()


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
                 (Enforced by the backend; Redis uses server-side eviction.)
        ttl: Time to live in seconds. Can be:
             - int/float: Fixed TTL in seconds
             - Callable: Function that returns TTL in seconds (evaluated at cache time)
             - None: Items never expire by time
        ignore_self: If True, ignores the first argument (self/cls) in cache key.
                     Useful for caching instance methods globally across instances.
        namespace: Cache namespace for grouped invalidation.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        locks: dict[str, asyncio.Lock] = {}
        stats = {"hits": 0, "misses": 0}
        ns_key = str(namespace)
        func_prefix = func.__qualname__

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            backend = get_backend()
            key_args = args[1:] if ignore_self and args else args
            key = _make_cache_key(func_prefix, *key_args, **kwargs)

            # Try cache first
            hit, result = await backend.get(ns_key, key)
            if hit:
                stats["hits"] += 1
                return result

            # Cache miss: synchronize concurrent fetches for the same key
            lock = locks.setdefault(key, asyncio.Lock())
            async with lock:
                # Double-check after acquiring lock
                hit, result = await backend.get(ns_key, key)
                if hit:
                    stats["hits"] += 1
                    return result

                # Compute result
                stats["misses"] += 1
                result = await func(*args, **kwargs)

            # Clean up lock to prevent unbounded growth
            locks.pop(key, None)

            # Calculate TTL (support dynamic TTL via callable)
            current_ttl = ttl() if callable(ttl) else ttl

            # Store in backend
            await backend.set(ns_key, key, result, current_ttl)

            return result

        def cache_clear():
            """Clear all cached entries for this function's namespace."""
            locks.clear()
            stats["hits"] = 0
            stats["misses"] = 0
            logger.info(f"Cache cleared for {func.__name__}")

        async def cache_set(*args, result):
            """Inject a value into the cache for the given arguments.

            Args are the function arguments (excluding self if ignore_self is True).
            This allows batch methods to populate individual cache entries.
            """
            backend = get_backend()
            key = _make_cache_key(func_prefix, *args)
            current_ttl = ttl() if callable(ttl) else ttl
            await backend.set(ns_key, key, result, current_ttl)

        async def cache_invalidate(*args):
            """Invalidate a specific cache entry without touching the rest of the namespace.

            Args are the function arguments (excluding self if ignore_self is True).
            """
            backend = get_backend()
            key = _make_cache_key(func_prefix, *args)
            await backend.delete(ns_key, key)
            logger.info(f"Cache explicitly invalidated for {func.__name__}")

        def cache_info() -> dict:
            """Return cache statistics for this function."""
            return {
                "func": func.__name__,
                "namespace": ns_key,
                "hits": stats["hits"],
                "misses": stats["misses"],
                "hit_rate": (
                    round(stats["hits"] / (stats["hits"] + stats["misses"]), 3)
                    if (stats["hits"] + stats["misses"]) > 0
                    else 0.0
                ),
            }

        wrapper.cache_clear = cache_clear
        wrapper.cache_set = cache_set
        wrapper.cache_invalidate = cache_invalidate
        wrapper.cache_info = cache_info
        wrapper.cache_namespace = ns_key

        # Register for namespace invalidation
        if ns_key not in _namespace_registry:
            _namespace_registry[ns_key] = []
        _namespace_registry[ns_key].append(wrapper)

        # Register for global stats lookup
        if ns_key not in _func_registry:
            _func_registry[ns_key] = []
        _func_registry[ns_key].append((func.__name__, cache_info))

        return wrapper

    return decorator


async def invalidate_namespace(namespace: CacheNamespace) -> None:
    """Clear all caches registered under a namespace.

    Args:
        namespace: The namespace to invalidate.
    """
    backend = get_backend()
    total_cleared = await backend.clear_namespace(str(namespace))
    if total_cleared > 0:
        logger.info(f"Invalidated namespace '{namespace}': cleared {total_cleared} entries")


async def invalidate_all_namespaces() -> None:
    """Clear all caches across every namespace."""
    backend = get_backend()
    total_cleared = await backend.clear_all()
    if total_cleared > 0:
        logger.info(f"Invalidated all namespaces: cleared {total_cleared} entries")


def get_all_cache_stats() -> dict[str, list[dict]]:
    """Return cache stats for every registered function, grouped by namespace.

    Returns:
        Dictionary mapping namespace names to lists of per-function stat dicts.
    """
    return {
        ns_key: [stats_fn() for _, stats_fn in funcs] for ns_key, funcs in _func_registry.items()
    }


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
    from bot.core.enums import ChannelIds
    from bot.services.locations_service import LocationsService

    if channel_id is None:
        channel_id = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS

    await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)
    await invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

    locations_svc = LocationsService(bot)
    await locations_svc._find_all_messages(channel_id)
    logger.info("Warmed ask rides message ID cache")


async def warm_ask_drivers_message_cache(bot, event=None) -> None:
    """Invalidate and re-populate the ask-drivers message ID cache.

    Call this after sending a new ask-drivers message.
    If event is None, warms all events in a single pass.

    Args:
        bot: The Discord bot instance.
        event: Optional AskRidesMessage enum value. If None, warms all events.
    """
    from bot.services.locations_service import LocationsService

    await invalidate_namespace(CacheNamespace.ASK_DRIVERS_MESSAGE_ID)

    locations_svc = LocationsService(bot)
    await locations_svc._find_all_driver_messages()
    logger.info("Warmed ask drivers message ID cache")


async def warm_ask_rides_reactions_cache(bot, event) -> None:
    """Invalidate and warm the ask-rides reactions cache for a specific event.

    Args:
        bot: The Discord bot instance.
        event: The AskRidesMessage event.
    """
    from bot.services.locations_service import LocationsService

    locations_svc = LocationsService(bot)

    await invalidate_namespace(CacheNamespace.ASK_RIDES_REACTIONS)
    # Warm up cache
    await locations_svc.get_ask_rides_reactions(event)
    event_name = event.name if hasattr(event, "name") else event
    logger.info(f"Warmed ask-rides reactions cache for {event_name}")


async def warm_ask_drivers_reactions_cache(bot, event=None) -> None:
    """Invalidate and warm the ask-drivers reactions cache for a specific event.

    Args:
        bot: The Discord bot instance.
        event: Optional AskRidesMessage event. If provided, selectively invalidates
               and warms only that event without touching the rest of the namespace.
    """
    from bot.core.enums import AskRidesMessage
    from bot.services.locations_service import LocationsService

    locations_svc = LocationsService(bot)

    if event:
        # Selectively invalidate and warm
        await locations_svc.get_driver_reactions.cache_invalidate(event)
        await locations_svc.get_driver_reactions(event)
        event_name = event.name if hasattr(event, "name") else event
        logger.info(f"Warmed specific ask-drivers reactions cache for {event_name}")
    else:
        # Full namespace invalidate and warm
        await invalidate_namespace(CacheNamespace.ASK_DRIVERS_REACTIONS)
        await locations_svc.get_driver_reactions(AskRidesMessage.FRIDAY_FELLOWSHIP)
        await locations_svc.get_driver_reactions(AskRidesMessage.SUNDAY_SERVICE)
        logger.info("Warmed full ask-drivers reactions cache namespace")
