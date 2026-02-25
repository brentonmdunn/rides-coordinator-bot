"""Cache backend abstraction for pluggable storage (in-memory or Redis)."""

import pickle
import time
from collections import OrderedDict
from typing import Any, Protocol

from bot.core.logger import logger


class CacheBackend(Protocol):
    """Protocol that all cache backends must implement."""

    async def get(self, namespace: str, key: str) -> tuple[bool, Any]:
        """Retrieve a value from the cache.

        Args:
            namespace: Cache namespace.
            key: Serialised cache key.

        Returns:
            (hit, value) — hit is True when a non-expired entry was found.
        """
        ...

    async def set(self, namespace: str, key: str, value: Any, ttl: int | float | None) -> None:
        """Store a value in the cache.

        Args:
            namespace: Cache namespace.
            key: Serialised cache key.
            value: The object to cache.
            ttl: Time-to-live in seconds, or None for no expiry.
        """
        ...

    async def delete(self, namespace: str, key: str) -> None:
        """Remove a single entry from the cache.

        Args:
            namespace: Cache namespace.
            key: Serialised cache key.
        """
        ...

    async def clear_namespace(self, namespace: str) -> int:
        """Delete every entry in *namespace*.

        Returns:
            Number of entries removed.
        """
        ...

    async def clear_all(self) -> int:
        """Delete every entry across all namespaces.

        Returns:
            Number of entries removed.
        """
        ...


# ---------------------------------------------------------------------------
# In-memory backend (default)
# ---------------------------------------------------------------------------


class InMemoryBackend:
    """OrderedDict-backed LRU cache — identical behaviour to the original."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._maxsize = maxsize
        # namespace -> OrderedDict[key, (value, timestamp, ttl)]
        self._stores: dict[str, OrderedDict] = {}

    def _ns(self, namespace: str) -> OrderedDict:
        if namespace not in self._stores:
            self._stores[namespace] = OrderedDict()
        return self._stores[namespace]

    async def get(self, namespace: str, key: str) -> tuple[bool, Any]:
        store = self._ns(namespace)
        if key not in store:
            return False, None
        value, timestamp, cached_ttl = store[key]
        if cached_ttl is not None and time.time() - timestamp > cached_ttl:
            del store[key]
            return False, None
        store.move_to_end(key)
        return True, value

    async def set(self, namespace: str, key: str, value: Any, ttl: int | float | None) -> None:
        store = self._ns(namespace)
        store[key] = (value, time.time(), ttl)
        store.move_to_end(key)
        while len(store) > self._maxsize:
            store.popitem(last=False)

    async def delete(self, namespace: str, key: str) -> None:
        store = self._ns(namespace)
        store.pop(key, None)

    async def clear_namespace(self, namespace: str) -> int:
        store = self._stores.get(namespace, OrderedDict())
        count = len(store)
        store.clear()
        return count

    async def clear_all(self) -> int:
        total = 0
        for store in self._stores.values():
            total += len(store)
            store.clear()
        return total


# ---------------------------------------------------------------------------
# Redis backend (production)
# ---------------------------------------------------------------------------


class RedisBackend:
    """Redis-backed cache using ``redis.asyncio``."""

    # All keys are prefixed so they don't collide with other Redis users.
    _KEY_PREFIX = "cache"

    def __init__(self, url: str = "redis://localhost:6379") -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(url, decode_responses=False)
        logger.info(f"RedisBackend initialised (url={url})")

    def _make_key(self, namespace: str, key: str) -> str:
        return f"{self._KEY_PREFIX}:{namespace}:{key}"

    def _ns_pattern(self, namespace: str) -> str:
        return f"{self._KEY_PREFIX}:{namespace}:*"

    async def get(self, namespace: str, key: str) -> tuple[bool, Any]:
        raw = await self._redis.get(self._make_key(namespace, key))
        if raw is None:
            return False, None
        return True, pickle.loads(raw)

    async def set(self, namespace: str, key: str, value: Any, ttl: int | float | None) -> None:
        data = pickle.dumps(value)
        rkey = self._make_key(namespace, key)
        if ttl is not None:
            await self._redis.setex(rkey, int(ttl), data)
        else:
            await self._redis.set(rkey, data)

    async def delete(self, namespace: str, key: str) -> None:
        await self._redis.delete(self._make_key(namespace, key))

    async def clear_namespace(self, namespace: str) -> int:
        keys: list[bytes] = []
        async for k in self._redis.scan_iter(match=self._ns_pattern(namespace)):
            keys.append(k)
        if keys:
            await self._redis.delete(*keys)
        return len(keys)

    async def clear_all(self) -> int:
        pattern = f"{self._KEY_PREFIX}:*"
        keys: list[bytes] = []
        async for k in self._redis.scan_iter(match=pattern):
            keys.append(k)
        if keys:
            await self._redis.delete(*keys)
        return len(keys)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_backend: CacheBackend = InMemoryBackend()


def get_backend() -> CacheBackend:
    """Return the active cache backend."""
    return _backend


def set_backend(backend: CacheBackend) -> None:
    """Swap the cache backend.  Call once at startup."""
    global _backend
    _backend = backend
    logger.info(f"Cache backend set to {type(backend).__name__}")
