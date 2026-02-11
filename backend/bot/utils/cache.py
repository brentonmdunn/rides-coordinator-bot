"""Simple async LRU cache with TTL support."""

import asyncio
import functools
import time
from collections import OrderedDict
from typing import Any, Callable, TypeVar

T = TypeVar("T")



def alru_cache(
    maxsize: int = 128, ttl: int | float | Callable[[], int | float] | None = None, ignore_self: bool = False
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
                    logger.info(f"Cache EXPIRED for {func.__name__} (age: {time.time() - timestamp:.1f}s, ttl: {cached_ttl}s)")
                    del cache[key]
                else:
                    # Move to end (most recently used)
                    cache.move_to_end(key)
                    logger.info(f"Cache HIT for {func.__name__} (age: {time.time() - timestamp:.1f}s, ttl: {cached_ttl}s, cache size: {len(cache)})")
                    return result

            # Compute result
            logger.info(f"Cache MISS for {func.__name__} - fetching new data (cache size: {len(cache)})")
            result = await func(*args, **kwargs)

            # Calculate TTL (support dynamic TTL via callable)
            current_ttl = ttl() if callable(ttl) else ttl
            if current_ttl is not None:
                logger.info(f"Cache stored with TTL: {current_ttl}s for {func.__name__}")

            # Add to cache with computed TTL
            cache[key] = (result, time.time(), current_ttl)
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
