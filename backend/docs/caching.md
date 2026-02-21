# Caching System

The bot uses a custom async LRU cache (`bot/utils/cache.py`) with TTL and namespace support to reduce Discord API calls. This document explains how the cache works, what's cached, and how invalidation is managed.

## Core: `@alru_cache` Decorator

The `alru_cache` decorator caches the return value of async functions. It supports:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `maxsize` | `int` | `128` | Maximum entries per function cache |
| `ttl` | `int`, `float`, `Callable`, or `None` | `None` | Time-to-live in seconds. `None` = never expires by time |
| `ignore_self` | `bool` | `False` | If `True`, excludes `self` from the cache key (shared across instances) |
| `namespace` | `CacheNamespace` | `DEFAULT` | Groups this cache for bulk invalidation |

### How It Works

1. **Cache key** is derived from the function arguments (excluding `self` if `ignore_self=True`)
2. On hit: checks TTL expiry → returns cached value or evicts stale entry
3. On miss:
   - Acquires a per-key `asyncio.Lock` to prevent **Cache Stampedes / Thundering Herds**.
   - If 10 concurrent requests arrive during a miss, 1 computes the result while the other 9 wait. Once populated, the 9 queueing requests return the newly cached data from memory immediately.
   - Computes the function, stores `(result, timestamp, ttl)` in an `OrderedDict`
4. LRU eviction: when `maxsize` is exceeded, the least-recently-used entry is removed

### Dynamic TTL

The `ttl` parameter can accept a callable that returns a TTL value at cache-time. This is used by `get_ask_rides_status()` to vary the TTL based on the current time of day.

```python
# Fixed TTL
@alru_cache(ttl=60)

# Dynamic TTL (evaluated each time a new entry is stored)
@alru_cache(ttl=_get_dynamic_ttl)
```

---

## Namespaces

Every cached function belongs to a `CacheNamespace` (defined in `bot/core/enums.py`). Namespaces group related caches so they can be invalidated together.

### Available Namespaces

| Namespace | Purpose | TTL | Functions |
|---|---|---|---|
| `ASK_RIDES_MESSAGE_ID` | Message IDs for ask-rides messages | 10 days | `_find_correct_message()` |
| `ASK_DRIVERS_MESSAGE_ID` | Message IDs for ask-drivers messages | 10 days | `_find_driver_message()` |
| `ASK_RIDES_REACTIONS` | Reaction data for ask-rides messages | 45 min | `list_locations()`, `get_ask_rides_reactions()`, `_get_usernames_who_reacted()` |
| `ASK_DRIVERS_REACTIONS` | Reaction data for ask-drivers messages | 45 min | `get_driver_reactions()` |
| `ASK_RIDES_STATUS` | Dashboard status for ask-rides jobs | Dynamic | `get_ask_rides_status()` |
| `DEFAULT` | Fallback (currently unused) | — | — |

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  _namespace_registry                     │
│  (global dict: namespace → list of OrderedDict caches)  │
├──────────────────────┬──────────────────────────────────┤
│ ASK_RIDES_MESSAGE_ID │ [_find_correct_message.cache]    │
├──────────────────────┼──────────────────────────────────┤
│ ASK_DRIVERS_MSG_ID   │ [_find_driver_message.cache]     │
├──────────────────────┼──────────────────────────────────┤
│ ASK_RIDES_REACTIONS  │ [list_locations.cache,            │
│                      │  get_ask_rides_reactions.cache,    │
│                      │  _get_usernames_who_reacted.cache]│
├──────────────────────┼──────────────────────────────────┤
│ ASK_DRIVERS_REACTIONS│ [get_driver_reactions.cache]      │
├──────────────────────┼──────────────────────────────────┤
│ ASK_RIDES_STATUS     │ [get_ask_rides_status.cache]      │
└──────────────────────┴──────────────────────────────────┘
```

When a function is decorated with `@alru_cache(namespace=...)`, its internal `OrderedDict` cache is registered in the `_namespace_registry` under that namespace. Multiple functions can share the same namespace.

---

## Invalidation

### Namespace Invalidation

```python
from bot.core.enums import CacheNamespace
from bot.utils.cache import invalidate_namespace, invalidate_all_namespaces

# Clear all caches in one namespace
invalidate_namespace(CacheNamespace.ASK_RIDES_MESSAGE_ID)

# Clear all caches across all namespaces
invalidate_all_namespaces()
```

### Per-Function Clear

```python
# Clear only one specific function's cache
get_ask_rides_status.cache_clear()
```

### Cache Warming Helpers

Centralized functions in `bot/utils/cache.py` that handle invalidation + re-population in one call:

```python
from bot.utils.cache import warm_ask_rides_message_cache, warm_ask_drivers_message_cache

# After sending new ask-rides messages (invalidates ASK_RIDES_STATUS + ASK_RIDES_MESSAGE_ID)
await warm_ask_rides_message_cache(bot, channel_id)

# After sending a new ask-drivers message (invalidates ASK_DRIVERS_MESSAGE_ID)
await warm_ask_drivers_message_cache(bot, event)
```

### When Invalidation + Warming Happens

| Trigger | Function Called | Namespaces Invalidated | Cache Warming |
|---|---|---|---|
| `run_ask_rides_all()` sends new messages | `warm_ask_rides_message_cache()` | `ASK_RIDES_STATUS`, `ASK_RIDES_MESSAGE_ID` | ✅ All `AskRidesMessage` types |
| `/ask-drivers` command sends a message | `warm_ask_drivers_message_cache()` | `ASK_DRIVERS_MESSAGE_ID` | ✅ The relevant day |
| Any User reacts/un-reacts | `_check_if_ask_message()` | `ASK_RIDES_REACTIONS` or `ASK_DRIVERS_REACTIONS` | ✅ Updates instantly |
| 20-min Cron | `run_periodic_cache_warming()` | `ASK_RIDES_REACTIONS` + `ASK_DRIVERS_REACTIONS` | ✅ Refreshes out-of-band Sheet edits |

**Cache warming** re-populates the cache immediately after invalidation so the next request is served from cache rather than hitting the Discord API. This combination of **Reaction-driven Invalidations** and **Cron-driven Periodics** means cache TTLs can be remarkably long (up to 45+ mins) completely safely without locking the data.

---

## Cached Functions Reference

### `_find_correct_message()` — `locations_service.py`

- **Namespace:** `ASK_RIDES_MESSAGE_ID`
- **TTL:** 10 days (864000s)
- **What it does:** Scans `channel.history()` to find the most recent ask-rides message matching an `AskRidesMessage` enum value
- **Why cached:** Channel history scans are expensive Discord API calls; message IDs don't change until new messages are sent

### `_find_driver_message()` — `locations_service.py`

- **Namespace:** `ASK_DRIVERS_MESSAGE_ID`
- **TTL:** 10 days (864000s)
- **What it does:** Scans `channel.history()` to find the most recent driver message matching an `AskRidesMessage` enum value
- **Why cached:** Same as above; driver message IDs are stable between sends

### `list_locations()` — `locations_service.py`

- **Namespace:** `ASK_RIDES_REACTIONS`
- **TTL:** 45 minutes (2700s)
- **What it does:** Aggregates reaction data (who reacted with what emoji) for ask-rides messages
- **Why cached:** Multiple dashboard requests within 45ms shouldn't re-fetch reactions

### `get_ask_rides_reactions()` — `locations_service.py`

- **Namespace:** `ASK_RIDES_REACTIONS`
- **TTL:** 45 minutes (2700s)
- **What it does:** Returns reaction breakdown (emoji → usernames) for a specific ask-rides message type
- **Why cached:** Called by the `/api/ask-rides/reactions/{type}` endpoint; avoids redundant `fetch_message` + `reaction.users()` calls

### `_get_usernames_who_reacted()` — `locations_service.py`

- **Namespace:** `ASK_RIDES_REACTIONS`
- **TTL:** 45 minutes (2700s)
- **What it does:** Returns the set of usernames who reacted to a specific message
- **Why cached:** Called by `list_locations()` and shares the same invalidation lifecycle

### `get_driver_reactions()` — `locations_service.py`

- **Namespace:** `ASK_DRIVERS_REACTIONS`
- **TTL:** 45 minutes (2700s)
- **What it does:** Returns reaction breakdown for driver messages
- **Why cached:** Reduces API calls when the dashboard polls for driver reaction data

### `get_ask_rides_status()` — `ask_rides.py`

- **Namespace:** `ASK_RIDES_STATUS`
- **TTL:** Dynamic (60–180s based on time of day)
- **What it does:** Returns status for all ask-rides jobs (enabled, paused, will_send, etc.)
- **Why cached:** Dashboard polls this frequently; status doesn't change between sends

---

## Adding a New Cached Function

1. Choose or create a `CacheNamespace` in `bot/core/enums.py`
2. Decorate your async function:
   ```python
   from bot.utils.cache import alru_cache
   from bot.core.enums import CacheNamespace

   @alru_cache(ttl=60, ignore_self=True, namespace=CacheNamespace.MY_NAMESPACE)
   async def my_function(self, arg1, arg2):
       ...
   ```
3. Add `invalidate_namespace(CacheNamespace.MY_NAMESPACE)` where the underlying data changes
4. Optionally warm the cache after invalidation by calling the function

> ⚠️ **Important:** All function arguments must be **hashable** (no `list`, `dict`, `set`). Use enums, tuples, strings, or ints as arguments to cached functions.
