# Architecture Review Findings

**Date:** 2026-05-07  
**Focus:** Maintainability and readability. Performance is a secondary concern.

## Architecture Rules (from CLAUDE.md)

```
Cog  ──┐
        ├──▶  Service  ──▶  Repository  ──▶  DB
API  ──┘
```

- Cogs and API routes are thin entry points — no business logic
- Services call repositories; routes/cogs call services only
- Repositories: `@staticmethod`, `session` as first param, never open their own sessions
- Enums in `bot/core/enums.py`, constants in `bot/utils/constants.py` or `api/constants.py`
- Logging via `bot/core/logger.py` — never `print()`

---

## Critical

### ~~CRIT-1 — Nonexistent Method Called at Runtime~~ ✅ RESOLVED

**File:** `api/routes/locations.py:73`

The route calls `service._group_locations_by_housing(...)` — this method does not exist. The actual method is `service.group_locations_by_housing(...)` (no leading underscore). This is a runtime `AttributeError` if that endpoint is hit.

**Fix:** Remove the leading underscore:
```python
# Wrong
grouped = service._group_locations_by_housing(...)

# Correct
grouped = service.group_locations_by_housing(...)
```

---

## High

### ~~HIGH-1 — Routes Calling Repositories Directly (6 violations)~~ ✅ RESOLVED

**Rule violated:** API routes must call services, not repositories.

| File | Repository Called Directly | Notes |
|---|---|---|
| `api/routes/feature_flags.py:39,65,86,89,93` | `FeatureFlagsRepository` | Re-implements toggle logic already in `FeatureFlagsService.modify_feature_flag()` |
| `api/routes/ask_rides.py:82,122,129` | `MessageScheduleRepository` | No `MessageScheduleService` exists; formatting logic duplicated from `bot/jobs/ask_rides.py` |
| `api/routes/admin_users.py:106,166` | `UserAccountsRepository` | `list_accounts` and `update_role` bypass `UserAccountsService` |
| `api/routes/me.py:88` | `UserAccountsRepository` | `switch_role` calls repo directly |
| `api/routes/reaction_log.py:94` | `RideReactionEventsRepository` | Grouping/formatting logic in the route |
| `api/routes/check_pickups.py:124` | `RideCoverageRepository` | Coverage query inline in route |

**Fixes applied:**
- `feature_flags.py`: Added `list_flags()`, `get_flag()`, `reinitialize_cache()` to `FeatureFlagsService`; route calls service only
- `ask_rides.py`: Created `MessageScheduleService` with `get_all_pauses()`, `set_pause()`, `clear_pause()`; route calls service only
- `admin_users.py` + `me.py`: Added `UserAccountsService.list_accounts()` and `UserAccountsService.update_role()`
- `reaction_log.py`: Moved grouping/sorting into `RideReactionLogService.get_grouped_events()`
- `check_pickups.py`: Uses `RideCoverageService.get_coverage_summary(ride_type)`

---

### ~~HIGH-2 — API Calling a Cog Directly for Business Logic~~ ✅ RESOLVED

**Files:** `bot/cogs/ride_coverage.py`, `api/routes/check_pickups.py:177`

`check_pickups.py` calls `bot.get_cog("RideCoverage")` to invoke `sync_ride_coverage()`. The cog contains the implementation. An API route calling a Discord cog is an antipattern — cogs are presentation layer for Discord, not a service layer.

**Fix applied:** Extracted `sync_ride_coverage`, `is_grouping_message`, and `extract_passengers` into `bot/services/ride_coverage_service.py`. Both the cog and the API route call the service.

---

### ~~HIGH-3 — Private Methods Called Across Module Boundaries (7 call sites)~~ ✅ RESOLVED

`LocationsService._find_correct_message()` and `._get_usernames_who_reacted()` are treated as public API by other modules:

- `api/routes/list_pickups.py:83`
- `api/routes/check_pickups.py:89,104,110,114`
- `api/routes/locations.py:73` (also the CRIT-1 bug above)
- `bot/cogs/reactions.py:279`
- `bot/services/group_rides_service.py:107,269,341`

**Fix applied:** Renamed both methods to remove the leading underscore in `LocationsService`. Updated all 7 call sites.

---

### ~~HIGH-4 — Business Logic in the `RideCoverage` Cog (311 lines)~~ ✅ RESOLVED

**File:** `bot/cogs/ride_coverage.py`

`sync_ride_coverage()`, `_is_grouping_message()`, and `_extract_passengers()` are pure business logic living in a cog. Cogs should only contain Discord event listeners and slash command entry points.

**Fix applied:** Moved all three methods into `bot/services/ride_coverage_service.py`. The cog delegates to the service.

---

## Medium

### MED-1 — Pickup Coverage Logic Duplicated in 3 Places

The sequence "find the correct ask-rides message → get reacting usernames → exclude Sunday class attendees" appears in:

1. `bot/services/locations_service.py` — `list_locations()` (canonical version)
2. `api/routes/check_pickups.py` — `get_pickup_coverage()` (~40 lines, re-implemented inline)
3. `bot/services/group_rides_service.py` — `_filter_class_attendees()` (partial)

**Fix:** Consolidate into `RideCoverageService.get_coverage_summary(ride_type)` and have all three call sites use it.

---

### MED-2 — Housing Group Response Formatting Duplicated

**Files:** `api/routes/list_pickups.py:108–134`, `api/routes/locations.py:77–114`

Both routes build a `housing_groups` dict by iterating `grouped_data["groups"]` with identical transformation logic.

**Fix:** Extract a `format_housing_groups_response(grouped_data)` helper (e.g., in `api/utils.py`) and call it from both routes.

---

### MED-3 — `ride_type` Returned as Plain String, Not Enum

**File:** `bot/services/ride_reaction_log_service.py:109–129`

`_detect_ride_type()` returns `"sunday_class"`, `"sunday"`, `"friday"`, `"wednesday"` as plain strings. These match `JobName` enum values but are not enforced. `RideReactionEvent.ride_type` is typed `Mapped[str | None]` with no constraint.

**Fix:** Create a `MessageRideType` enum (or reuse/rename an existing one) and have `_detect_ride_type()` return `MessageRideType | None`. Update the model column to use it. Note: the existing `RideType` enum refers to pickup/dropoff direction — rename it to `RideDirection` to avoid confusion.

---

### MED-4 — `logger.error(f"...{e}")` in Except Blocks — Drops Tracebacks

The following use `logger.error(...)` inside `except` blocks, which loses the full traceback. Per CLAUDE.md, use `logger.exception(...)` instead.

- `bot/jobs/ask_rides.py:219`
- `bot/jobs/ask_drivers.py:39`
- `bot/services/thread_service.py:44,61,80`
- `bot/repositories/community_events_repository.py:123`
- `bot/utils/checks.py:85`

**Fix:** Replace `logger.error(f"...{e}")` with `logger.exception("...")` in all `except` blocks. Never include `{e}` in the format string — `logger.exception` appends the traceback automatically.

---

### MED-5 — `get_ask_rides_status` Dashboard Helper in Jobs File

**File:** `bot/jobs/ask_rides.py` (593 lines total)

`get_ask_rides_status` (110 lines) and related helpers `find_message_in_history` and `get_next_run_time` are dashboard/API utilities living in a jobs file. The file has four mixed responsibilities: message construction, job runners, cache warming, and API helpers.

**Recommended split:**
- Message formatters → `bot/utils/ride_messages.py`
- Status/dashboard helpers → `bot/services/ask_rides_service.py`
- Job runners + cache warming → `bot/jobs/ask_rides.py` (slimmed down)

---

### MED-6 — Emoji in Production Log Messages

**Files:** `lifecycle.py`, `database.py`, several API routes

Many `logger.info` calls use decorative emoji (✅, ❌, 🔧, 👤, ⏸️). This is inconsistent with the structured `[txn:xxx]` log format defined in CLAUDE.md and makes log scraping harder.

**Fix:** Remove emoji from all logger calls in non-test code.

---

## Low

### LOW-1 — Typo "Widlcard" in Discord Message

**File:** `bot/jobs/ask_rides.py:271`

User-visible Discord message and log both say "Widlcard detected." Should be "Wildcard".

---

### LOW-2 — `CategoryIds` is `StrEnum` While All Other ID Enums Are `IntEnum`

**File:** `bot/core/enums.py:101`

`CategoryIds(StrEnum)` stores IDs as strings, requiring callers to cast: `int(CategoryIds.NEW_RIDES)`. All other ID enums (`ChannelIds`, `RoleIds`) are `IntEnum`.

**Fix:** Either convert to `IntEnum` (preferred) or add a comment documenting why it must remain a string enum.

---

### LOW-3 — `living_to_pickup` Module-Level Dict Should Be a Constant

**File:** `bot/services/group_rides_service.py:43–55`

This mapping never changes and maps between two enum types. It belongs in `bot/utils/constants.py` or `bot/core/enums.py`.

---

### LOW-4 — `RideOptionsSchema = RideOption` Unused Alias

**File:** `bot/services/locations_service.py:31`

This alias is defined but not used anywhere in the file. Remove it.

---

### LOW-5 — `LocationsService` Is Overloaded with Delegation Wrappers

`LocationsService` has five `_find_*` / `_get_*` delegation methods that pass straight through to `ReactionService` with no added logic. This creates confusion about which service to use. Callers should either use `ReactionService` directly, or `LocationsService` should expose clean public methods without the forwarding boilerplate (see HIGH-3 above).

---

### LOW-6 — Frontend: `LoadingSkeleton` Duplicated in `ReactionLog.tsx`

**File:** `frontend/src/pages/ReactionLog.tsx:197–220`

A `LoadingSkeleton` component is defined inline in this file. A shared `LoadingSkeleton` already exists at `frontend/src/components/LoadingSkeleton.tsx`. The inline version should be removed.

---

### LOW-7 — Frontend: `console.error` in Production Code Paths

**Files:**
- `frontend/src/components/MapLinks.tsx:42`
- `frontend/src/hooks/usePickups.ts:57`
- `frontend/src/components/GroupRides.tsx:71`
- `frontend/src/components/RouteBuilder/RouteBuilder.tsx:447`

These log errors to the console with no user-visible fallback. Remove or gate behind `import.meta.env.DEV`.

---

### LOW-8 — `RouteBuilder.tsx` Inline Hook and Persistence Helpers

**File:** `frontend/src/components/RouteBuilder/RouteBuilder.tsx` (616 lines)

`useIsMobile` is defined inline (should be in `src/hooks/`). localStorage/URL persistence helpers (lines 64–170) should be extracted to a `useRouteBuilderPersistence` hook. The component is still manageable but extracting these would reduce it to a true orchestrator.
