# Codebase Suggestions

Suggestions organized by category and priority. Focus: **maintainability**.

---

## Bugs

### B1 — `lookup_time` can return `None` instead of raising

`bot/utils/locations.py:93` — If Dijkstra never reaches the target, the function returns `None`. Callers (e.g. `calculate_pickup_time`, `make_route`) do arithmetic on the result without a `None` check, which would produce a `TypeError` at runtime.

**Fix:** Raise a `ValueError` when no path is found instead of returning `None`.

### B2 — `LLMService.generate_ride_groups` is synchronous but called with `await`

`bot/services/llm_service.py:56` — The method is not `async`, yet `_process_ride_grouping` calls it from an async context. Because `self.llm.invoke()` is a blocking HTTP call, this blocks the entire event loop (Discord heartbeats, other commands).

**Fix:** Run the blocking LLM call inside `asyncio.to_thread()` or switch to an async LLM client.

### B3 — Global mutable `prev_response` in `llm_service.py`

`bot/services/llm_service.py:25` — `prev_response` is a module-level global mutated inside `generate_ride_groups`. If two concurrent requests hit the LLM service, they'll stomp each other's value. This also makes the code harder to test.

**Fix:** Move `prev_response` into the retry state or pass it as a local variable.

### B4 — `_check_if_ask_message` creates a new `LocationsService` on every reaction

`bot/cogs/reactions.py:169` — Instantiating `LocationsService(self.bot)` on every reaction event is wasteful and bypasses any instance-level caching.

**Fix:** Use `self.locations_cog.service` (already stored at `cog_load`) instead of constructing a new instance.

### B5 — `send_error_to_discord` signature mismatch in `ask_drivers.py`

`bot/jobs/ask_drivers.py:40` — Calls `send_error_to_discord(bot, e)`, but the function signature is `send_error_to_discord(error_msg: str, error=None, tb_text=None)`. The `bot` object would be coerced to a string message, and the actual exception would land in `error` as the string representation. This silently produces a mangled error report.

**Fix:** Call `send_error_to_discord(f"Error in ask_drivers: {e}", error=e)`.

### B6 — `ReactionAction` enum in a separate file from other enums

`bot/core/reaction_enums.py` — The project rule states *"All enums MUST live in `bot/core/enums.py`"*. `ReactionAction` breaks this rule.

**Fix:** Move `ReactionAction` to `bot/core/enums.py`.

### B7 — `time_helpers` functions use naive `datetime.now()` inconsistently

Several functions in `bot/utils/time_helpers.py` use `datetime.now()` (naive, server-local) while others use `datetime.now().astimezone(la_tz)` (LA timezone). For example, `is_ride_cycle_active()` (line 155) and `get_next_date_str()` (line 85) use naive time, but `is_in_ride_day_window()` (line 45) uses LA time. The bot is likely deployed in UTC, so these will give wrong results.

**Fix:** Standardize all time functions to use `datetime.now(tz=pytz.timezone("America/Los_Angeles"))`.

### B8 — `WILDCARD_DATES` and `CLASS_DATES` are hardcoded constants

`bot/jobs/ask_rides.py:46-47` — These lists contain specific dates (`"6/20"`, `"6/27"`, `"6/29"`) that will become stale every year. There is no mechanism to update them without a code deploy.

**Fix:** Move to a database table or config file, or at minimum add a year component and a note on when to update.

---

## Refactors

### R1 — Extract common validation boilerplate from API routes

Multiple API routes (`group_rides.py`, `list_pickups.py`, `ask_rides.py`, `check_pickups.py`) repeat the same pattern: validate `ride_type`, convert `message_id` to int, convert `channel_id` to int, call `get_bot()` and check `None`. This is 20+ lines duplicated across 4+ files.

**Fix:** Create a shared dependency or utility (e.g., a FastAPI `Depends` function) that validates and parses these common parameters.

### R2 — `LocationsService` is too large (740 lines)

`bot/services/locations_service.py` handles CSV syncing, message finding, reaction fetching, location sorting, housing grouping, embed building, driver reactions, and caching. This violates single-responsibility.

**Fix:** Split into focused services:
- `CsvSyncService` — handles Google Sheets sync
- `ReactionService` — handles reaction fetching and caching
- `HousingGroupService` — handles location grouping and embed building
- Keep `LocationsService` as a thin coordinator

### R3 — `GroupRidesService` is too large (699 lines)

Similar to `LocationsService`, this service mixes LLM interaction, ride grouping logic, Discord message formatting, and API response formatting.

**Fix:** Extract:
- Ride grouping/assignment logic into a domain module
- Discord formatting into a presenter/formatter
- Keep the service as orchestrator

### R4 — Hardcoded channel IDs as default parameters

`api/routes/group_rides.py:29` and `api/routes/list_pickups.py:29` hardcode `"939950319721406464"` as the default channel ID in the Pydantic model. This duplicates the enum value in `ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS`.

**Fix:** Use `str(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS))` as the default, or better, resolve it server-side.

### R5 — Direct `AsyncSessionLocal()` usage scattered across services

Many services (e.g., `feature_flags_service.py`, `whois_service.py`, `non_discord_rides_service.py`) open `AsyncSessionLocal()` inline. This:
- Makes testing harder (can't inject a test session)
- Duplicates session lifecycle management
- Violates the layering rule (services should call repositories, not manage sessions directly)

**Fix:** Have services accept a session via dependency injection, or use a unit-of-work pattern.

### R6 — Repositories mix Discord API calls with database operations

`bot/repositories/thread_repository.py` has methods like `add_user_to_thread()`, `remove_user_from_thread()`, and `get_thread_members()` that call Discord API. Repositories should only handle database operations per the architectural rules.

**Fix:** Move Discord API calls to the service layer.

### R7 — Commented-out code in `job_scheduler.py`

`bot/cogs/job_scheduler.py` has ~40 lines of commented-out job registrations. This is dead code that makes it harder to understand which jobs are actually active.

**Fix:** Remove the commented-out blocks. Use version control history if they're needed again.

### R8 — `example.py` API route should be removed or gated

`api/routes/example.py` contains a `/api/discord/send-message` endpoint that sends messages to a hardcoded Discord channel. This is a development artifact that probably shouldn't be in production.

**Fix:** Remove it, or gate it behind `APP_ENV == "local"`.

### R9 — Duplicated housing group filter lists

`bot/services/locations_service.py:645-661` defines housing group filters (Scholars, Warren + Pepper Canyon, Rita, Off Campus) inline. The `SCHOLARS_LOCATIONS` constant is imported, but the Warren/Pepper Canyon/Rita filters are hardcoded strings.

**Fix:** Extract all housing filter definitions to `constants.py` for a single source of truth.

### R10 — `@feature_flag_enabled` decorator hits the database on every invocation

`bot/utils/checks.py:74` — The decorator opens a new database session on every command invocation to check a feature flag, even though there's already an in-memory cache in `FeatureFlagsRepository._cache`.

**Fix:** Check the cache first (like `FeatureFlagsRepository.get_feature_flag_status` does), and only fall back to DB if the cache is empty.

### R11 — Missing `__init__.py` / `__all__` exports in packages

The `bot/services/`, `bot/repositories/`, `bot/utils/`, and `api/routes/` packages don't have meaningful `__init__.py` files. This means imports are always fully qualified, which is fine, but explicit `__all__` exports would make the public API clearer.

### R12 — Inconsistent error handling patterns

Some endpoints return error responses in the response body (`GroupRidesResponse(success=False, error=...)`), while others raise `HTTPException`. For example, `group_rides.py` returns response-body errors for validation but uses HTTP 503 for bot not initialized. This inconsistency makes frontend error handling harder.

**Fix:** Pick one pattern. Recommendation: Use `HTTPException` for all errors and let FastAPI's exception handler produce consistent responses.

### R13 — `bot/api.py` does not load extensions in local environment

`bot/api.py:46` — `if APP_ENV != "local": await load_extensions(bot)` means cogs are never loaded locally when running the API, making local development testing incomplete.

### R14 — Magic strings for emoji reactions

Emoji strings like `"🍔"`, `"🏠"`, `"✳️"`, `"🪨"`, `"📖"` are scattered across `ask_rides.py`, `locations_service.py`, `driver_service.py`. These should be centralized.

**Fix:** Add an `Emoji` enum or constants dict in `enums.py` or `constants.py`.

---

## Features

### F1 — Automated stale-data cleanup for `NonDiscordRides`

The `delete_past_pickups` job exists in `non_discord_rides_service.py` but is commented out in `job_scheduler.py`. Past rides accumulate indefinitely in the database.

**Fix:** Re-enable the scheduled job or add a database-level TTL.

### F2 — API rate limiting

There is no rate limiting on any API endpoint. A misbehaving client could hammer the LLM endpoint (`POST /api/group-rides`) and burn through API quota.

**Fix:** Add FastAPI rate limiting middleware (e.g., `slowapi`).

### F3 — Health check should verify bot and database connectivity

`api/routes/health.py` returns `{"status": "ok"}` unconditionally. It doesn't check if the bot is connected or the database is reachable.

**Fix:** Add checks for bot readiness and a simple DB ping.

### F4 — Frontend error boundary

The React frontend (`Home.tsx`) has no error boundary. If any component throws, the entire page crashes with a white screen.

**Fix:** Add a React error boundary component wrapping the main layout.

### F5 — Frontend has no loading/skeleton states

Components like `PickupLocations`, `GroupRides`, etc. don't show loading indicators while data is being fetched, leading to layout shifts.

### F6 — Centralized API error handling in frontend

`frontend/src/lib/api.ts` has a minimal `apiFetch` wrapper that doesn't handle HTTP errors, parse error responses, or surface user-friendly messages.

**Fix:** Add a response interceptor that checks `res.ok`, parses error bodies, and throws typed errors.

### F7 — Add pre-commit hooks

There is no `.pre-commit-config.yaml`. Linting and formatting (`ruff`, `eslint`) rely on developers remembering to run them manually.

**Fix:** Add a pre-commit config with ruff, eslint, and potentially `prettier` for the frontend.

### F8 — Database migrations for schema changes

The codebase uses Alembic (based on project structure), but there's no evidence of migration files being actively managed. Schema changes through `models.py` modifications could lead to drift.

**Fix:** Ensure Alembic migrations are generated for every model change and tracked in CI.

### F9 — Observability: structured logging and metrics

The logging system is well-implemented with transaction IDs, but there are no application metrics (request latency, cache hit rates, LLM response times, job execution counts).

**Fix:** Add a lightweight metrics library (e.g., `prometheus-fastapi-instrumentator`) for API metrics.

### F10 — Test coverage for API routes

The test suite exists under `backend/tests/` but appears focused on unit tests for services and utilities. API route integration tests would catch issues like the response model mismatches and auth middleware behavior.
