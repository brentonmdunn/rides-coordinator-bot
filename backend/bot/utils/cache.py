"""Simple async LRU cache with TTL support."""

import functools
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any, TypeVar

from bot.core.logger import logger

T = TypeVar("T")


def alru_cache(
    maxsize: int = 128,
    ttl: int | float | Callable[[], int | float] | None = None,
    ignore_self: bool = False,
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
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        cache: OrderedDict = OrderedDict()

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
            """Clear all cached entries."""
            cache.clear()
            logger.info(f"Cache cleared for {func.__name__}")

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator
