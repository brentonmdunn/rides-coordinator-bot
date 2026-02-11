"""Simple async LRU cache with TTL support."""

import asyncio
import functools
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")



def alru_cache(
    maxsize: int = 128, ttl: int | float | None = None, ignore_self: bool = False
) -> Callable:
    """
    Async Least Recently Used (LRU) cache decorator with Time To Live (TTL).

    Args:
        maxsize: Maximum number of items to keep in the cache.
        ttl: Time to live in seconds. If None, items never expire by time.
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
                result, timestamp = cache[key]

                # Check if expired
                if ttl is not None and time.time() - timestamp > ttl:
                    del cache[key]
                else:
                    # Move to end (most recently used)
                    cache.move_to_end(key)
                    return result

            # Compute result
            result = await func(*args, **kwargs)

            # Add to cache
            cache[key] = (result, time.time())
            cache.move_to_end(key)

            # Enforce maxsize
            if len(cache) > maxsize:
                cache.popitem(last=False)

            return result

        def cache_clear():
            cache.clear()

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator
