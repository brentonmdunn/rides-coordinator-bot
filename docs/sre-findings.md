# SRE Reliability Findings

Audit date: 2026-05-13  
Audited by: Claude (SRE review)

---

## Legend

| Status | Meaning |
|---|---|
| `open` | Not yet addressed |
| `in-progress` | Work underway |
| `done` | Resolved |
| `wontfix` | Accepted risk, documented |

Severity: **CRITICAL** → **HIGH** → **MEDIUM** → **LOW**

---

## Site availability during Discord outages

When `DISABLE_DISCORD_BOT=true` (or bot is otherwise down), the website splits:

| Feature | Available? |
|---|---|
| Login, auth, user management, feature flags, reaction log, route builder, user preferences, cache stats | ✅ Yes — DB-only routes |
| Group rides, list pickups, check pickups, send ask-rides | ❌ No — return 503 via `require_bot()` |

The 503 responses are graceful (no crashes). The site remains usable for admin/read workflows during outages.

---

## Planned Feature: Discord Circuit Breaker

**Goal:** Eliminate the need to manually set `DISABLE_DISCORD_BOT=true` and restart during Discord API outages.

### How it works

1. **Auto-detection** — two signals:
   - discord.py's `on_disconnect` / `on_resumed` events fire immediately when the WebSocket drops
   - Background job polls `https://discordstatus.com/api/v2/summary.json` every 60s to detect sustained outages

2. **Runtime toggle** — a `DiscordCircuitBreaker` module holds a runtime flag. When tripped:
   - Bot WebSocket is gracefully closed (stops jobs from hammering the dead API)
   - FastAPI API stays up; bot-dependent routes return 503 as they do today
   - When the outage clears, the bot task is restarted in-process — no env var change, no restart needed

3. **Admin override** — `POST /api/admin/discord/disable` and `POST /api/admin/discord/enable` endpoints let operators manually trip/clear the breaker

**Status:** `open` — not yet implemented  
**Files to create/modify:** `bot/core/discord_circuit_breaker.py`, `bot/cogs/discord_health_monitor.py`, `api/routes/admin_discord.py`, `bot/api.py`

---

## CRITICAL

### C-1 — No validation of required env vars at startup
**Status:** `done`  
**Files:** `backend/main.py:16`, `backend/bot/api.py:22`, `backend/api/app.py:71`

`TOKEN`, `CLOUDFLARE_TEAM_DOMAIN`, `CLOUDFLARE_AUD`, and `REDIS_URL` are consumed without validation. Missing vars either cause the app to start healthy and fail silently later, or crash with a cryptic library error.

**Fix:**
```python
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    logger.error("CRITICAL: TOKEN is not set")
    sys.exit(1)
```
Apply the same pattern to Cloudflare and Redis vars in `app.py` / `lifecycle.py`.

---

### C-2 — Startup sequence has no error handling
**Status:** `done`  
**File:** `backend/main.py:20-28`

`startup()`, `load_extensions()`, and `bot.start(TOKEN)` are all called bare. Any failure crashes the process with no recovery or meaningful log context.

**Fix:**
```python
try:
    await startup()
except Exception:
    logger.exception("Startup failed")
    sys.exit(1)
```

---

### C-3 — DB migrations can fail silently and block all deployments
**Status:** `done`  
**Files:** `backend/entrypoint.sh:5`, `backend/Dockerfile.preprod`

`alembic upgrade head` runs under `set -e` with no messaging. A failed migration restarts the container in a loop with no diagnostic output. `Dockerfile.preprod` has no entrypoint at all — migrations never run on preprod deploys with schema changes.

**Fix:**
```bash
echo "Running migrations..."
if ! alembic upgrade head; then
    echo "ERROR: Migration failed. Manual intervention required."
    exit 1
fi
```
Add the same entrypoint to `Dockerfile.preprod`.

---

### C-4 — Migrations not tested for downgrade in CI
**Status:** `done`  
**File:** `.github/workflows/migrations.yaml`

CI only tests `alembic upgrade head`. Broken downgrades are discovered at the worst moment — during an emergency rollback.

**Fix:**
```yaml
- name: Test downgrade
  run: |
    uv run alembic downgrade -1
    uv run alembic upgrade head
```

---

### C-5 — Multiple Alembic heads in migration history
**Status:** `done`  
**File:** `backend/alembic/versions/cf1c49fb43ca_merge_...py`

A merge migration exists indicating the history branched. Two concurrent PRs with migrations can create divergent heads that break the next deployment.

**Fix:** Add a CI check:
```bash
heads=$(uv run alembic heads | wc -l)
if [ "$heads" -gt 1 ]; then echo "Multiple heads detected"; exit 1; fi
```

---

## HIGH

### H-1 — All external HTTP calls lack timeouts
**Status:** `done`  
**Files:** `backend/bot/services/csv_sync_service.py:38`, `backend/api/routes/auth_discord.py:104`, `backend/bot/repositories/calendar_repository.py:34`

- CSV sync: `httpx.AsyncClient().get(URL)` with no timeout — hangs forever on stalled endpoints
- Discord OAuth: three sequential `httpx` calls with no timeout — login hangs if Discord API is slow
- Calendar: uses synchronous `requests.get()` in an async codebase — **blocks the event loop**, freezing all bot responsiveness

**Fix:**
```python
# All httpx calls:
async with httpx.AsyncClient(timeout=10.0) as client: ...

# Calendar — replace requests with httpx:
async with httpx.AsyncClient(timeout=10.0) as client:
    response = await client.get(ICAL_URL)
```

---

### H-2 — Redis has no connection timeout and no fallback
**Status:** `done`  
**File:** `backend/bot/utils/cache_backends.py:139`

`aioredis.from_url()` connects lazily — no test at startup. First cache miss after Redis goes down fails with a cryptic error. Combined with `restart: unless-stopped` and infinite retries, a Redis outage can cause an indefinite restart loop.

**Fix:** Test connectivity at startup with a timeout:
```python
try:
    await asyncio.wait_for(backend._redis.ping(), timeout=5.0)
except Exception:
    logger.warning("Redis unavailable, falling back to in-memory cache")
    # Don't call set_backend — keep InMemoryBackend default
```

---

### H-3 — No database connection pool configuration
**Status:** `done`  
**File:** `backend/bot/core/database.py:21`

`create_async_engine(DATABASE_URL, echo=False)` uses SQLAlchemy defaults. Under concurrency spikes, connections aren't capped and stale connections after a DB restart aren't recycled.

**Fix:**
```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

---

### H-4 — Cloudflare key cache never expires
**Status:** `done`  
**File:** `backend/api/auth.py:27`

`_cloudflare_keys` is a global set once on first request and never invalidated. After Cloudflare rotates keys, every auth request fails until the process is manually restarted.

**Fix:** Store a timestamp and refresh every hour:
```python
if _cloudflare_keys is None or time.time() - _cloudflare_keys_fetched_at > 3600:
    # refetch
```

---

### H-5 — Auth session middleware: DB failure returns 500 instead of 401
**Status:** `done`  
**File:** `backend/api/auth_session.py:68`

The DB query in the session middleware has no try/catch. A transient DB error returns 500; the frontend doesn't treat 500 as an auth failure so the user sees a crash instead of being redirected to login.

**Fix:**
```python
try:
    async with AsyncSessionLocal() as db_session:
        auth_session = await AuthService.get_session(db_session, session_id_plain)
except Exception:
    logger.exception("DB error during session validation")
    return Response("Unauthorized", status_code=401)
```

---

### H-6 — Health check misreports bot status
**Status:** `done`  
**File:** `backend/api/routes/health.py:29`

`bot.is_ready()` only checks the Discord WebSocket handshake. If extensions fail to load (caught and swallowed), the bot reports healthy while commands silently fail. The DB check is read-only — a DB in read-only mode reports healthy.

**Fix:** Track failed extension loads; for DB, test a write. Include both in the health response.

---

### H-7 — No restart limits on Docker containers
**Status:** `done`  
**File:** `backend/deployment/docker-compose.yaml`

`restart: unless-stopped` with no `restart_policy.max_attempts` means a crashing container (bad migration, bad env var) restarts indefinitely, consuming resources.

**Fix:**
```yaml
restart_policy:
  condition: on-failure
  max_attempts: 5
  delay: 10s
```

---

### H-8 — EventSource in ReactionLog has no error handler
**Status:** `done`  
**File:** `frontend/src/pages/ReactionLog.tsx:245`

The SSE stream is opened with no `onerror` callback. When the backend closes the connection or errors, the stream silently stops and the user sees stale data indefinitely.

**Fix:**
```ts
es.onerror = () => {
    setStreamError(true)
    es.close()
}
```

---

### H-9 — OSRM route geometry fetch has no error state
**Status:** `done`  
**File:** `frontend/src/components/RouteBuilder/useRouteGeometry.ts:57`

On fetch failure the catch block logs to console but sets no state. The component renders without route lines or ETA, appearing broken with no explanation.

**Fix:** Set an `error` state in the catch block and render a visible fallback.

---

### H-10 — AuthGuard returns `null` before redirect fires
**Status:** `done`  
**File:** `frontend/src/components/AuthGuard.tsx:32`

On a 401, the component returns `null` (blank screen) while waiting for a `useEffect` to redirect. If the component unmounts before the effect runs, the user is stuck on a blank page.

**Fix:**
```tsx
if (error?.status === 401) {
    return <Navigate to="/login" replace />
}
```

---

### H-11 — Dockerfile.preprod missing migrations entrypoint
**Status:** `done` (covered by C-3)  
**File:** `backend/Dockerfile.preprod:50`

The preprod image runs the app directly with no `ENTRYPOINT` script. Migrations never run on preprod deploys with schema changes.

---

## MEDIUM

### M-1 — LLM JSON parsing uses hardcoded byte offsets
**Status:** `done`  
**File:** `backend/bot/services/llm_service.py:111`

```python
llm_result = json.loads(ai_response.content[8:-3])
```
If the response is shorter than 8 characters this silently produces garbage or raises `IndexError`. Any output format change from the model breaks parsing.

**Fix:** Use `re.search` to extract JSON blocks, then validate with a Pydantic model before use.

---

### M-2 — LLM retry catches all exceptions
**Status:** `done`  
**File:** `backend/bot/services/llm_service.py:50`

`retry=tenacity.retry_if_exception_type(Exception)` retries on auth errors, schema errors, and other permanent failures. 4 attempts × 5s = 15s of wasted latency on non-transient errors.

**Fix:** Only retry on `httpx.TransportError` and rate-limit exceptions from the Gemini SDK.

---

### M-3 — Bot shutdown has no timeout
**Status:** `done`  
**File:** `backend/bot/api.py:65`

`await bot.close()` followed by `await bot_task` — if Discord is unreachable at shutdown, this hangs indefinitely. The supervisor force-kills the process, leaking DB connections.

**Fix:**
```python
await asyncio.wait_for(bot.close(), timeout=10.0)
```

---

### M-4 — Feature flags stale cache after update
**Status:** `done`  
**File:** `backend/bot/repositories/feature_flags_repository.py:93`

Cache is updated after DB commit, creating a race condition between concurrent flag updates.

---

### M-5 — No error boundary on lazy-loaded admin components
**Status:** `done`  
**File:** `frontend/src/pages/Home.tsx:90`

`FeatureFlagsManager`, `UserManagement`, and `SystemActions` are wrapped in `<Suspense>` with no `ErrorBoundary`. If any throws, the error propagates to the top-level boundary and takes down the entire app.

**Fix:**
```tsx
<ErrorBoundary fallback={<div>Admin tools unavailable</div>}>
  <Suspense fallback={...}>...</Suspense>
</ErrorBoundary>
```

---

### M-6 — `refetchOnReconnect: false` leaves stale data permanently
**Status:** `done`  
**File:** `frontend/src/components/RideCoverageCheck.tsx:26`

Queries with `refetchOnReconnect: false` will never recover after a network interruption. The user reconnects and sees indefinitely stale data.

**Fix:** Remove `refetchOnReconnect: false` from any query where eventual consistency matters.

---

### M-7 — No database backup strategy
**Status:** `done`  
**File:** `backend/deployment/docker-compose.yaml`

SQLite lives in a Docker volume with no documented backup process. A bad migration or corruption has no recovery path.

**Fix:** Add a pre-migration backup to `entrypoint.sh`:
```bash
cp /app/db/bot.db /app/db/bot.db.bak-$(date +%Y%m%d%H%M%S) || true
```

---

### M-8 — Frontend deploy script uses `/tmp` for `.gitkeep`
**Status:** `done`  
**File:** `deploy-frontend.sh`

`/tmp` can be cleared by the OS mid-script. If it is, the `.gitkeep` restore silently fails and git tracks the `admin_ui` directory as modified.

**Fix:** Use a backup path within the repo directory instead of `/tmp`.

---

### M-9 — Error reporter silently no-ops during startup/shutdown
**Status:** `done`  
**File:** `backend/bot/core/error_reporter.py:28`

`send_error_to_discord()` silently no-ops if the bot isn't ready. Initialization failures (the most critical ones) never surface to admins.

**Fix:** Fall back to writing to stderr when the bot is unavailable.

---

### M-10 — ADMIN_EMAILS not validated at startup
**Status:** `done`  
**File:** `backend/bot/core/database.py:89`

Comma-separated emails are split and used with no format validation. An invalid entry (e.g. `"user3"`) gets added to the DB and can break auth flows that use email as a key.

**Fix:**
```python
import re
for email in admin_emails:
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        logger.error(f"Invalid email in ADMIN_EMAILS: {email}")
        sys.exit(1)
```

---

## LOW

### L-1 — `/health` and `/metrics` are unauthenticated
**Status:** `done`  
**Files:** `backend/api/routes/health.py`, `backend/api/app.py:94`

The health endpoint returns connection status details; `/metrics` exposes request rates and error counts. Both aid reconnaissance. Restrict `/metrics` to internal network or require a static token.

---

### L-2 — Frontend deploy script `/tmp` race (see M-8)

---

### L-3 — Error channel missing is not handled gracefully
**Status:** `done`  
**File:** `backend/bot/core/error_reporter.py`

If `ERROR_CHANNEL_ID` references a deleted channel, the send fails with no fallback. Wrap in try/catch and fall back to logging.

---

### L-4 — Health check bot-ready check is racy
**Status:** `done` (covered by H-6)  
**File:** `backend/api/routes/health.py:29`

`bot.is_ready()` reflects local in-process state only — not whether the bot can actually send messages to Discord. See H-6 for full details.

---

## Summary

| Severity | Count | Open | Done |
|---|---|---|---|
| CRITICAL | 5 | 0 | 5 |
| HIGH | 11 | 0 | 11 |
| MEDIUM | 10 | 0 | 10 |
| LOW | 4 | 0 | 4 |
| **Total** | **30** | **0** | **30** |

### Suggested resolution order

1. **This week (CRITICAL):** C-1 env var validation, C-2 startup error handling, C-3 migration entrypoint fix
2. **This week (HIGH):** H-1 add timeouts to all HTTP calls, H-5 session middleware catch block, H-10 AuthGuard blank page fix
3. **This sprint:** H-2 Redis fallback, H-3 DB pool config, H-4 Cloudflare key TTL, H-7 Docker restart limits, H-8 EventSource error handler
4. **This sprint:** C-4/C-5 CI migration tests, H-6 health check improvements
5. **Next sprint:** M-1 through M-10, L-1 through L-4
6. **Planned feature:** Discord circuit breaker (auto-detect outages, no-restart toggle)
