# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Repository Layout

Monorepo with three deployables:

- **`backend/`** — Python 3.13 app: two Discord bots (`discord.py`) — **RideBot** (ride coordination) and **StonesBot** (event threads) — and a FastAPI web API that all run **in the same process** (the bots are started inside FastAPI's lifespan). Split into `shared/` (infrastructure), `ridebot/` (ride-specific code), and `stonesbot/` (event-thread code) — see "Backend Architecture" below.
- **`frontend/`** — React 19 admin SPA (Vite + Tailwind CSS v4 + shadcn/ui). Built output is copied into `backend/admin_ui/` and served by the backend in production.
- **`portfolio/`** — Separate static site deployed to GitHub Pages (independent of the app).

Also: `deploy/` (Docker Compose update script with rollback), `docs/` (architecture/auth/deployment docs), `deploy-frontend.sh` (copies `frontend/dist/` → `backend/admin_ui/`).

---

## Commands

### Backend (run from `backend/`)

Always use `uv` to run Python and Python tools.

```bash
uv run python main.py                 # Run the Discord bot only
uv run python run_api.py              # Run API + bot together (uvicorn api.app:app on :8000)

uv run invoke lint                    # Ruff linter
uv run invoke format                  # Ruff formatter
uv run invoke fix                     # Ruff autofix
uv run invoke all                     # lint + fix + format
uv run ty check                       # Type check (or: uv run invoke typecheck)

uv run invoke test                    # All tests (pytest, verbose)
uv run pytest tests/unit/test_foo.py                 # Single file
uv run pytest tests/unit/test_foo.py::test_name -v   # Single test

uv run invoke migrate -m "description"   # Generate Alembic migration (autogenerate)
uv run alembic upgrade head              # Apply migrations
```

Set `DISABLE_DISCORD_BOT=true` for API-only mode (no bot login, no jobs).

### Frontend (run from `frontend/`)

```bash
npm run dev          # Vite dev server
npm run build        # tsc -b && vite build
npm run lint         # ESLint
npm test             # Vitest
npx tsc --noEmit     # Type check only
```

### After modifying code (do not ask before running these)

- Python: `uv run invoke format`, `uv run invoke lint`, `uv run ty check`
- Frontend: `npm run lint`, `npx tsc --noEmit`

---

## Backend Architecture

### Entry points & lifecycle

The process runs **N Discord bots** (separate Discord applications/tokens) in one event loop, alongside the FastAPI web API.

- `backend/main.py` — bot-only entry point: `resolve_enabled_bots()`, `startup()` once, then `run_bot(spec, token)` for every enabled bot concurrently via `asyncio.gather`.
- `backend/run_api.py` — runs `uvicorn api.app:app`; bots are started/stopped via `bot_lifespan()` in `shared/core/lifespan.py` inside FastAPI's lifespan, so **bots and API share one process**. Bot instances are globally accessible via `shared.core.bot_instance.get_bot(name)`.
- Cog auto-loading lives in `shared/core/lifecycle.py` (`load_extensions(bot, spec)`), discovering modules via `pkgutil` over `spec.cog_packages`; `spec.priority_extensions` stems load first (alphabetical after that), and `spec.testing_cog_package` loads last, only when `APP_ENV=local`. Failures are tracked per bot in `_failed_extensions` (`get_failed_extensions() -> dict[BotName, set[str]]`) and exposed by `/health`.
- Startup also seeds feature flags (from `FeatureFlagNames`) and admin accounts (from `ADMIN_EMAILS`).

### Multi-bot registry (`shared/core/bots.py`)

- `BotSpec` is the static config for one bot: `name` (`BotName`), `token_env`, `cog_packages`, `intents`, `kill_switch_flag`, plus optional `priority_extensions` and `testing_cog_package`.
- `BOT_REGISTRY: tuple[BotSpec, ...]` lists every bot this process can run; its order is also the error-reporting fallback priority (see below). `get_spec(name)` looks one up (`KeyError` if unregistered); `bot_package_names()` returns the top-level packages of every registered bot's `cog_packages` (used by the import-boundary test).
- Two bots are registered: **RideBot** (`token_env="RIDEBOT_TOKEN"`, `cog_packages=("ridebot.cogs", "shared.cogs")`, `kill_switch_flag=FeatureFlagNames.RIDEBOT`, loads `job_scheduler` first and `ridebot.cogs_testing` last when local) and **StonesBot** (`token_env="STONESBOT_TOKEN"`, `cog_packages=("stonesbot.cogs", "shared.cogs")`, `kill_switch_flag=FeatureFlagNames.STONESBOT`, intents are default + `members` only — no `message_content`, no priority/testing extensions).
- `resolve_enabled_bots() -> list[EnabledBot]` reads each bot's token env var **at call time** (a blank value counts as missing) and decides which bots start this run — see the token behavior table below. It's called once, right after the `DISABLE_DISCORD_BOT` check and before `startup()`, so a misconfigured deploy fails fast without touching the DB.
- **`get_bot(name: BotName)` requires a bot name** — there is no singleton. Call sites (`api/dependencies.py`, `api/routes/*`, `shared/core/error_reporter.py`, `ridebot/core/scheduler_control.py`) always pass an explicit `BotName`. `ty check` is the safety net that catches call sites that haven't picked one.
- **`current_bot_var`** (`shared/core/bot_context.py`) is a `ContextVar[BotName | None]` set as the *first* statement of each bot's `run_bot()` task. Asyncio copies context on `create_task`, so it reaches event listeners, slash commands, and APScheduler job callbacks spawned from inside that task — but **not** API requests (uvicorn's own tasks), process `startup()`, or anything run via `loop.run_in_executor` (use `asyncio.to_thread` if you need it to propagate). Read it with `get_current_bot_name()`. Logging (`BotNameFilter`) and the `@bot_enabled` kill switch both key off this contextvar.

#### Token behavior (`resolve_enabled_bots`)

| `DISABLE_DISCORD_BOT` | `APP_ENV` | Tokens set | Result |
|---|---|---|---|
| `true` | any | any | API-only. No tokens are read, no bots start, scheduled jobs don't run |
| unset/`false` | `preprod`/`prod` | all | Every bot starts |
| unset/`false` | `preprod`/`prod` | some/none missing | `logger.critical` per missing var, then `sys.exit(1)` — the container never becomes healthy, so the deploy rolls back |
| unset/`false` | `local` | all | Every bot starts |
| unset/`false` | `local` | some missing | `logger.warning` per skipped bot; the rest still start. A skipped bot loads no cogs, is absent from `/health`, and its commands don't exist |
| unset/`false` | `local` | none | `sys.exit(1)`: "No bot tokens set — set at least one `<BOT>_TOKEN`, or `DISABLE_DISCORD_BOT=true` for API-only mode" |

A token that's set but **invalid** behaves the same in every environment: that bot's `run_bot` task ends with `LoginFailure` before becoming ready, `bot_lifespan()` (or `main.py`) logs it and `sys.exit(1)`s rather than hanging forever.

### Health and the per-bot kill switch

- `GET /health` reports `{"status": "ok"|"degraded", "database": ..., "bots": {"<name>": "connected"|"unavailable"}, "failed_extensions": {...}}` for every bot in `get_enabled_bot_names()`. It returns **HTTP 503** (not 200) whenever `status == "degraded"` — any enabled bot not ready, or any failed cog load, makes the deploy's health check fail and triggers rollback. A bot skipped locally for lack of a token doesn't count.
- Every cog command gated by the old single `FeatureFlagNames.BOT` flag now uses the bare decorator `@bot_enabled` (`shared/utils/checks.py`) instead of naming a flag directly. At call time it resolves `get_current_bot_name()`, looks up `get_spec(name).kill_switch_flag`, and delegates to the existing `feature_flag_enabled` check — so a cog moved between bots (or placed in `shared/cogs/`) needs no edits. If no bot name is set (e.g. some unit tests), it fails closed with a warning.

### `shared/` vs `ridebot/`

The backend is split into two top-level packages, plus `api/`:

- **`shared/`** — infrastructure every bot needs: DB engine/session (`shared/core/database.py`), models (`shared/core/models.py`), enums (`shared/core/enums.py`), logging (`shared/core/logger.py`), error reporting (`shared/core/error_reporter.py`), bot lifecycle (`shared/core/lifecycle.py`, `shared/core/lifespan.py`, `shared/core/bot_instance.py`), feature flags, auth, user accounts/preferences (`shared/services/`, `shared/repositories/`), and the `/help` cog (`shared/cogs/help.py`). **`shared/` must never import a bot package.**
- **`ridebot/`** — everything ride-specific: cogs, services, repositories, jobs, and utils for ride coordination.
- **`stonesbot/`** — event-thread cogs, services, repositories, and jobs (`stonesbot/cogs/`, `stonesbot/services/`, `stonesbot/repositories/`, `stonesbot/jobs/`). It runs its own APScheduler instance in `stonesbot/cogs/job_scheduler.py` (`StonesJobScheduler`), separate from RideBot's. The `EventThreads` and `WeeklyEventsAnnouncement` models stay in `shared/core/models.py`.
- **Rule for where new code goes:** code lives in `shared/` only if it's infrastructure or is actually used by at least two bots. Otherwise it lives in the owning bot package (`ridebot/` or `stonesbot/`) and is promoted to `shared/` later, when a second consumer appears.
- **Import-boundary test** (`backend/tests/unit/test_import_boundaries.py`): a pure-AST check enforcing that `shared` imports no bot package, and that bot packages don't import each other or `api` — so `ridebot` and `stonesbot` can never import from one another.

### Layers

```
Cog  ──┐
        ├──▶  Service  ──▶  Repository  ──▶  DB
API  ──┘
```

- **Cogs** (`ridebot/cogs/`, `stonesbot/cogs/`, plus `shared/cogs/help.py`): Discord slash commands and event listeners; auto-loaded per bot. `ridebot/cogs_disabled/` are never loaded; `ridebot/cogs_testing/` load only when `APP_ENV=local` (StonesBot has no disabled/testing cog packages).
- **Services** (`ridebot/services/`, `stonesbot/services/`, plus infra services in `shared/services/`): Business logic layer. Cogs call services, never repositories directly.
- **Repositories** (`ridebot/repositories/`, `stonesbot/repositories/`, plus infra repositories in `shared/repositories/`): Data access layer. All SQL/database queries live here.
- **Jobs** (`ridebot/jobs/`, `stonesbot/jobs/`): Scheduled tasks run by APScheduler. Each bot owns its own scheduler cog (`ridebot/cogs/job_scheduler.py`, `stonesbot/cogs/job_scheduler.py`), both pinned to `LA_TZ` from `shared/utils/constants.py`. Disabled ride jobs go in `ridebot/jobs_disabled/`.
- **API** (`api/`): FastAPI routes in `api/routes/`, auth in `api/auth.py` / `api/auth_session.py`, middleware in `api/middleware/`, rate limiting via slowapi in `api/rate_limit.py`.

### Pickup info

Pickup info (who the bot gives rides to, and where they live) has no Google
Sheets sync — it's owned entirely by `PickupInfoService` (`ridebot/services/pickup_info_service.py`),
backed by the `locations` table. Coordinators and admins manage it through the web
API (`api/routes/pickup_info.py`, `/api/pickup-info`) and the admin UI's `/pickup-info` page.
New riders register themselves via a Discord button/modal (the registration view
in `ridebot/views/pickup_info.py`) posted in their new-rides channel.

Every rider has a **phone number** (`locations.phone`; helpers in `ridebot/utils/phone.py`).
Only US 10-digit numbers (optional `+1`, any common separators) count as valid; they're
stored as bare digits and shown as `(858) 555-1234`. The Discord form requires the field
but **accepts invalid numbers** (Discord modals can't validate a regex), storing them as
typed and flagging them in the ride-coordinator notice. Web edits are strict (400 on invalid,
except re-saving an unchanged value). The admin Pickup Info page highlights rows whose phone
is invalid or missing (`phone_status` on the API response).

### Ask-rides "Something else" button

Ask-rides announcement embeds carry a persistent **Something else** button
(`ridebot/views/ask_rides_other.py`, one `AskRidesOtherView` per `AskRidesMessageType`,
registered in the `Reactions` cog's `cog_load`). It opens a modal and forwards the rider's
text to `SERVING__RIDE_COORDINATORS` via `AskRidesOtherService`
(`ridebot/services/ask_rides_other_service.py`). Gated by `FeatureFlagNames.ASK_RIDES_OTHER_BUTTON`
plus RideBot's kill switch; clicks on past-week announcements are refused. Locally,
`/test-ask-rides-other` posts the embed (with the button when the flag is on) in the current channel.

### Pickup summaries

Two RideBot jobs post the `/list-pickups-friday` and `/list-pickups-sunday` embeds to
`SERVING__RIDE_COORDINATORS` (defaults: Friday 11AM, Saturday 4PM LA), each with two markdown links:
`<FRONTEND_BASE_URL>/?overview=<friday|sunday>#reactions` (Ask Rides Overview on that tab) and
`<FRONTEND_BASE_URL>/?settings=pickup-summaries` (opens Site Settings scrolled to Pickup summaries).
Both params are read once and stripped from the URL via `useConsumeSearchParam`
(`frontend/src/hooks/`), so they never appear when navigating there manually.

- Gates, in order: `@bot_enabled`, `FeatureFlagNames.FRIDAY_/SUNDAY_PICKUPS_SUMMARY_JOB`, then the
  per-slot `enabled` toggle in `pickup_summary_settings` (checked at run time; the job stays scheduled).
- Day/time are editable in Site Settings (`/api/ask-rides/pickup-summaries`) and applied live via
  `reschedule_job`. Defaults and allowed days: `ridebot/utils/pickup_summary_defaults.py`.
- Logic: `ridebot/services/pickup_summary_service.py`; embeds come from
  `LocationsService.build_pickups_embeds`, shared with the slash commands. Skips silently in
  Wednesday-fellowship season (Friday), when the ask-rides job is paused, or when no ask-rides
  message was found this week. `/send-pickups-summary <friday|sunday>` posts the same message in the
  current channel on demand (ignores the toggle and flags).

### Temporary drivers

Ride coordinators can give someone the Driver role for a limited time via `/add-temp-driver`
(also `/remove-temp-driver`, `/list-temp-drivers`) or the "Temporary" option in the dashboard's
Drivers tab (`POST /api/drivers/temp`). Both call `TempDriverService`
(`ridebot/services/temp_driver_service.py`), backed by the `temp_driver_grants` table.

- Durations: `ridebot/utils/duration_parsing.py` — relative (`12h`, `3d`, `2w`) or a date
  (`10/5`, `2026-10-05`, meaning 11:59 PM LA that day). Default 1 week, max 90 days
  (`ridebot/utils/constants.py`).
- Expiry is **polling**: `ridebot/jobs/temp_drivers.py` runs every 5 minutes and once at startup,
  gated by `@bot_enabled` + `FeatureFlagNames.TEMP_DRIVER_EXPIRY_JOB`. A sweep with nothing to do
  logs nothing above DEBUG (`log_job_quiet` + `QuietJobFilter` in `shared/core/logger.py`).
- Grants, extensions, early removals and expiries are announced in `SERVING__RIDE_COORDINATORS`
  (via `resolve_channel_id`, never pinging the driver). A slash command run in that channel uses
  its own reply as the announcement; anywhere else (or from the web) the bot posts separately.
- Re-granting a temp driver replaces the expiry; permanent drivers are refused. Adding a temp
  driver permanently from the Drivers tab clears the grant; removing a Driver role by hand in
  Discord also clears it (`role_monitor.py`).

### Weekly events announcement (StonesBot)

Every Sunday at 6PM LA time, StonesBot posts one embed to
`ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS` listing the coming week's calendar events
(the Monday after the run through the following Sunday) — only days that have events, each as a bold heading with its events bulleted underneath — and then
deletes the previous week's announcement. An empty week still posts, saying nothing is
scheduled.

- Schedule: `stonesbot/cogs/job_scheduler.py` (`StonesJobScheduler`, its own APScheduler instance).
- Job: `stonesbot/jobs/weekly_events.py` — gated by `@bot_enabled` plus `FeatureFlagNames.WEEKLY_EVENTS_ANNOUNCEMENT_JOB`.
- Logic: `stonesbot/services/weekly_events_service.py`.
- Events come from the iCal feed (`ICAL_URL`) via `CalendarRepository.get_event_summaries_by_date()`
  in `shared/repositories/calendar_repository.py`, which downloads the feed once and expands it per day.
- **Only allowlisted events are announced** — the feed carries much more than belongs in the post.
  `ALLOWED_EVENT_SUMMARIES` holds exact names (currently `Regular Worship Service`) and
  `ALLOWED_EVENT_SUBSTRINGS` holds substrings (currently `Wildcard Sunday`); both match
  case-insensitively. Widen the announcement by adding to those tuples, not by editing the filter.
- **Everything else on a day that has an allowed event rides along as an "extra"**
  (`WeeklyEventsService.extra_events`). Extras get no line and no event of their own: they are
  hung off that day's first embed bullet as indented `↳` sub-bullets (`EXTRA_BULLET_PREFIX`,
  which uses non-breaking spaces because Discord collapses ordinary leading whitespace) and
  folded into the Discord scheduled event's description as `Also today: Child Dedication`.
  Extras on a day with no allowed event are dropped, and an already-created scheduled event is
  never edited to pick up new ones.
- Recognized entries also get a **Discord scheduled event** via `stonesbot/services/discord_events_service.py`.
  Today only `Regular Worship Service` maps to one: an external event, 10:30a–12p LA time on the calendar
  date, located at `Jonas Salk Elementary School` (the feed's entries are all-day, so time and place are
  pinned in the service). Duplicates are avoided by matching name + start time against
  `guild.scheduled_events`, so re-running the job creates nothing new; past start times are skipped because
  Discord rejects them. This runs last and is best-effort — a failure never costs the channel its
  announcement. **StonesBot needs the Manage Events permission** for this.
- The posted message id is stored in `weekly_events_announcements` (`stonesbot/repositories/weekly_events_announcement_repository.py`)
  so deletion survives restarts. The new message is sent *before* the old one is deleted, so a failed
  send never leaves the channel empty; a previous message that is already gone is logged and skipped.

### Centralizing Shared Logic (No Duplication Between Cogs and API)

Cogs and API routes are both **thin entry points** — they handle input/output for their respective interfaces (Discord vs. HTTP) but must not contain business logic themselves.

**Rules:**
- Never duplicate logic between a cog and an API route — extract it into a service method.
- Cogs call services. API routes call services. Neither calls repositories directly.
- If you find yourself copy-pasting logic from a cog into a route (or vice versa), stop and put it in a service instead.

### Key Patterns

- Use `async`/`await` everywhere — the DB uses aiosqlite + async SQLAlchemy.
- Never use hardcoded strings for enums — always use `shared/core/enums.py` (e.g., `JobName`, `FeatureFlagNames`, `DaysOfWeek`, `RideType`, `ChannelIds`, `RoleIds`, `AccountRoles`).
- Constants go in `ridebot/utils/constants.py` (ride) or `shared/utils/constants.py` (infra) or `api/constants.py` (API-side).
- Logging goes through `shared/core/logger.py` — never use `print()`.
- Cache layer (`ridebot/utils/cache.py`, `shared/utils/cache_backends.py`): Redis backend with in-memory fallback in local mode; namespaced keys for grouped invalidation.
- Feature flags: stored in the `feature_flags` table, seeded from `FeatureFlagNames` on startup, accessed via `feature_flags_repository.py`. Local dev auto-disables job/message flags to prevent spam (`disable_features_for_local_env()`).
- Error reporting: `shared/core/error_reporter.py:send_error_to_discord()` posts exceptions to the `ERROR_CHANNEL_ID` channel (gated by the `SEND_ERRORS_TO_DISCORD` flag; skipped locally; falls back to stderr). It picks which bot posts via `get_current_bot_name()` first, then `BOT_REGISTRY` order, then any other ready bot.
- Health check: `GET /health` reports per-bot readiness, DB connectivity, and failed cog loads for every enabled bot (bypasses auth); see "Health and the per-bot kill switch" above — it's 503, not always 200.

### Adding a new bot

Full walkthrough with examples and Discord portal setup: `docs/adding-a-bot.md`.

1. Add `BotName.<NEW>` and `FeatureFlagNames.<NEW>` to `shared/core/enums.py`.
2. Write an Alembic data migration seeding the new kill-switch flag row (decide its initial `enabled` value — e.g. copied from an existing bot's flag, as `stonesbot` copies `ridebot`'s).
3. Add a `BotSpec` entry to `BOT_REGISTRY` in `shared/core/bots.py`: `token_env`, `cog_packages` (include `"shared.cogs"` if the new bot should get `/help`), and an `intents` factory with only what the bot's cogs actually need.
4. Create a top-level `<new>/` package with `cogs/`, plus `services/`/`repositories/` as needed. New models still go in `shared/core/models.py`.
5. Never import across bot packages — if the new bot needs something living in another bot's package, promote it to `shared/` instead. The import-boundary test (`tests/unit/test_import_boundaries.py`) enforces this.
6. Add `<NEW>_TOKEN` to `.env.example`, `Dockerfile.preprod`, and the server env files (`.env.dev`/`.env.preprod`/`.env.prod`), in deploy order: Discord app setup first, then the token in server env, then deploy.
7. Set up the Discord application: enable whatever privileged intents the bot needs, invite it with the required scopes/permissions, and give it access to the `ERROR_CHANNEL_ID` channel.
8. Update `CLAUDE.md` and `docs/bot-commands.md` (and `docs/feature-flags.md` for the new kill-switch flag).

---

## Authentication

Auth is controlled by the `AUTH_PROVIDER` env var (`cloudflare` | `self`, default `cloudflare`). Both providers expose the same contract — a middleware that sets `request.state.user = {"email": str}` — so all route-level role checks (`require_admin`, `require_ride_coordinator` in `api/auth.py`) are unaffected by which provider is active.

### Providers

| `AUTH_PROVIDER` | Middleware | When to use |
|---|---|---|
| `cloudflare` | `api/auth.py` — verifies `Cf-Access-Jwt-Assertion` header | Current default; keep during cutover |
| `self` | `api/auth_session.py` — reads `rides_session` httpOnly cookie | Active self-hosted auth |

### Self-hosted flow (`AUTH_PROVIDER=self`)

1. Unauthenticated request to `/api/*` → **401**. Frontend `AuthGuard` redirects to `/login`.
2. User clicks "Log in with Discord" → `GET /api/auth/discord/login` → redirects to Discord with random `state` cookie.
3. Discord redirects back to `GET /api/auth/discord/callback` → state validated, code exchanged, `GET /users/@me` called.
4. **3-tier identity matching** (in `shared/services/auth_service.py`):
   - By `discord_user_id` (stable — used after first login)
   - By `discord_username` where `discord_user_id IS NULL` (first login for invited users)
   - By `email` where `discord_user_id IS NULL` (grandfather path for pre-existing CF Access accounts)
   - No match → redirect to `/login?error=not_invited`
5. Session row created in `auth_sessions` table. `rides_session` httpOnly cookie + `csrf_token` readable cookie set. Redirect to frontend.
6. On subsequent requests, middleware validates session, enforces CSRF on mutations (`X-CSRF-Token` header).

### Invite-only access

Users must be pre-invited before they can log in. Admins invite by Discord username via `POST /api/admin/users/invite` (UI in `UserManagement`). This creates a `user_accounts` row with `discord_username` and no email; email is populated on first login.

**Exception:** rows seeded from `ADMIN_EMAILS` env var and any existing rows from the CF Access era are automatically grandfathered — they match by email on first Discord login and get their Discord identity linked.

### Sessions

- 256-bit random token in cookie; SHA-256 hash stored in `auth_sessions` table.
- 30-day sliding expiry (`SESSION_TTL_DAYS`), throttled touch (max one DB write per 5 min per session).
- Logout (`POST /api/auth/logout`) deletes the row server-side before clearing cookies.

### Local development

- `APP_ENV=local` (default) → mock user `dev@example.com` injected on every request. No Discord round-trip.
- To test the real OAuth flow locally: set `AUTH_PROVIDER=self`, `LOCAL_USE_DISCORD_OAUTH=true`, and the `DISCORD_OAUTH_*` vars. Add `http://localhost:8000/api/auth/discord/callback` to the Discord app's redirect URIs. Your email must be in `ADMIN_EMAILS` so the account is seeded on startup.

### Key files

| File | Purpose |
|---|---|
| `api/auth.py` | CF Access middleware + `require_admin` / `require_ride_coordinator` dependencies |
| `api/auth_session.py` | Self-hosted session cookie middleware |
| `api/routes/auth_discord.py` | OAuth flow routes (`/login`, `/callback`, `/logout`) |
| `shared/services/auth_service.py` | Identity matching cascade + session lifecycle |
| `shared/repositories/auth_sessions_repository.py` | `auth_sessions` table access |
| `frontend/src/components/AuthGuard.tsx` | Route guard — redirects to `/login` on 401 |
| `frontend/src/lib/auth.ts` | CSRF cookie helper + `logout()` |

---

## Database Conventions

### Stack

- **SQLite** via **aiosqlite** (async driver) + **SQLAlchemy** (async ORM).
- Engine/session factory in `shared/core/database.py` (`pool_pre_ping=True`, `pool_recycle=3600`); models in `shared/core/models.py`; DB file at `backend/db/bot.db` (override with `DATABASE_URL`).

### Migrations

- Managed by **Alembic** (config: `backend/alembic.ini`, versions: `backend/alembic/versions/`).
- Generate: `uv run invoke migrate -m "description"` (wraps `alembic revision --autogenerate`).
- Apply: `uv run alembic upgrade head`. In Docker, `entrypoint.sh` backs up the SQLite file then runs `upgrade head` automatically before the app starts.
- CI (`migrations.yaml`) rejects multiple heads, model drift, and broken downgrades.

### Repository Conventions

Three rules apply to every DB repository:

1. **`@staticmethod` only** — repositories hold no instance state, so all methods are static.
2. **`session: AsyncSession` as the first parameter** — every DB method accepts a session. Repositories never open their own sessions.
3. **Consistent naming** — file: `<domain>_repository.py`, class: `<Domain>Repository`.

The **service layer owns the unit-of-work**: services open sessions with `async with AsyncSessionLocal() as session:` and pass them into repository calls. Never write raw SQL in cogs or services.

```python
# ✅ Correct — service opens session, passes to repo
async with AsyncSessionLocal() as session:
    result = await FooRepository.get_by_id(session, foo_id)

# ❌ Wrong — repo opens its own session
class FooRepository:
    async def get_by_id(self, foo_id):
        async with AsyncSessionLocal() as session:
            ...
```

**Exception:** repositories that wrap Discord objects (e.g., `EventsRepository`, which holds `self.bot`) legitimately use instance methods because they hold instance state unrelated to DB sessions. This exception does not apply to any DB repository.

---

## Logging Conventions

### Setup

- Logging is configured in `shared/core/logger.py` (console + rotating file handlers → `logs/bot.log`).
- Every file uses its own per-module logger:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- **Never** use `from shared.core.logger import logger` — that's the root logger. Always create a per-module logger with `getLogger(__name__)`.
- **Never** use `print()` for diagnostics — always use `logger`.

### Log Levels

| Level      | When to use |
|------------|-------------|
| `DEBUG`    | Detailed diagnostic info only useful during development (variable values, intermediate state, cache hits) |
| `INFO`     | Normal operational events: startup, shutdown, sync completion, commands invoked, successful operations |
| `WARNING`  | Recoverable problems or expected-but-notable conditions: bot not ready, missing optional config, network timeouts, invalid user input in API routes |
| `ERROR`    | Failures that affect a specific operation but don't crash the app (use sparingly — prefer `exception` in `except` blocks) |
| `CRITICAL` | App-wide failures (rarely used) |

### Exception Logging

- **In `except` blocks, always use `logger.exception("message")`** — it automatically appends the full traceback. Never use `logger.error(f"...{e}")` in an except block; the traceback will be missing.
- **Do NOT include the exception in the format string** — `logger.exception` already includes it:
  ```python
  # ✅ Correct
  except Exception:
      logger.exception("Failed to sync locations")

  # ❌ Wrong — redundant, prints exception twice
  except Exception as e:
      logger.exception(f"Failed to sync locations: {e}")

  # ❌ Wrong — no traceback
  except Exception as e:
      logger.error(f"Failed to sync locations: {e}")
  ```
- **Never silently swallow exceptions.** If an `except` block returns a default value, still log the exception first.

### Transaction IDs & Context

- Slash commands: wrap with `@log_cmd` (from `shared.core.logger`) to auto-assign a transaction ID and log the command invocation.
- Scheduled jobs: wrap with `@log_job` to auto-assign a transaction ID.
- API requests: transaction IDs are injected via `api/middleware/access_logger.py`.
- Log format includes `[txn:%(txn_id)s]` and `[%(user_email)s]` for tracing. `%(name)s` shows the full module path, so don't prefix messages with the module name manually.

### Common Patterns

- **Cog/command entry points**: Log at `INFO` with user-relevant context (command name, arguments, day, message_id).
- **Service operations**: Log start/completion at `INFO`; intermediate steps at `DEBUG`.
- **Repository queries**: Generally no logging needed for routine queries. Log exceptions and unusual conditions.
- **Bot not ready / missing optional config**: Use `WARNING`, not `ERROR`.
- **Sending errors to Discord**: Always pair `logger.exception(...)` with `await send_error_to_discord(...)` for unexpected errors in user-facing flows.

---

## Frontend Conventions

React 19 SPA in `frontend/`, built with Vite and Tailwind CSS v4. Path alias `@` → `src/`.

### Architecture

- **Entry/routing**: `src/main.tsx` — react-router routes, React Query provider, `ThemeProvider` (system/light/dark via `.dark` class), top-level `ErrorBoundary`, Sonner toasts. Non-home pages are lazy-loaded.
- **Pages** (`src/pages/`): `Home.tsx` is the main dashboard with role-gated sections; `Learn`, `ReactionLog`, `Locations`, `Login`.
- **Components** (`src/components/`): shadcn/ui primitives in `ui/` (new-york style), feature components at top level (e.g., `RouteBuilder/`, `AskRidesDashboard/`, `UserManagement`), shared layout in `shared/`.
- **API layer**: `src/lib/api.ts` — `apiFetch()` wrapper resolves `VITE_API_URL` (dev: `http://localhost:8000`; prod: same origin), sends `credentials: include`, attaches `X-CSRF-Token` from the cookie on mutating methods, and throws `ApiError` on non-2xx. Use it for all backend calls.
- **Server state**: @tanstack/react-query. Types in `src/types.ts`; helpers in `src/lib/utils.ts`.

### Standards

- Use TypeScript — no `any` types.
- Run `npm run lint` and `npx tsc --noEmit` before committing frontend changes.
- Environment configs: `.env.development` (local) and `.env.production` (see `frontend/ENV_CONFIG.md`).

### Color Tokens

Always use the OKLCH semantic tokens defined in `frontend/src/index.css` — never hardcode Tailwind palette utilities like `bg-blue-600`, `text-slate-500`, or `bg-zinc-800`.

| Semantic intent | Use |
|---|---|
| Page/default text | `text-foreground` |
| Secondary/subdued text | `text-muted-foreground` |
| Page background | `bg-background` |
| Card/surface | `bg-card`, `text-card-foreground` |
| Subtle fill (inputs, rows) | `bg-muted`, `bg-muted/50` |
| Popovers/dropdowns | `bg-popover` |
| Dividers | `border-border` |
| Info (blue) | `bg-info/10`, `text-info-text`, `border-info/30` |
| Success (green) | `bg-success/10`, `text-success-text`, `border-success/30` |
| Warning (yellow) | `bg-warning/10`, `text-warning-text`, `border-warning/30` |
| Destructive (red) | `bg-destructive/10`, `text-destructive-text`, `border-destructive/30` |

Exceptions: `emerald` (route builder map accent) and `amber` (revert button) are intentional design choices and may stay.

---

## Testing Conventions

### Backend

- Tests live in `backend/tests/` (`unit/`, `integration/`, `api/`). pytest config is in `pyproject.toml` (`asyncio_mode = "strict"`).
- `tests/unit/conftest.py` provides Discord fakes (`FakeBot`, `FakeCommandTree`, etc.) for testing cogs without a live bot.
- Use `pytest-asyncio` for async tests; `pytest-cov` is available for coverage.

### Frontend

- Vitest via `npm test`.

---

## Docker & Deployment

- `backend/Dockerfile` (prod, port 8000) and `backend/Dockerfile.preprod` (port 7999, `APP_ENV=preprod`); two-stage uv builds, image `brentonmdunn/ride-bot` (preprod: `ride-bot-preprod`).
- `backend/entrypoint.sh` backs up the SQLite DB to a timestamped file, runs `alembic upgrade head`, then execs uvicorn.
- `backend/deployment/docker-compose.yaml`: redis + ride-bot with health checks; `deploy/update.sh` does pull-and-restart with automatic rollback on failed health check.
- Frontend ships inside the backend image: CI builds `frontend/dist/` and copies it to `backend/admin_ui/` (locally: `./deploy-frontend.sh`).
- Env files in `backend/`: `.env.dev`, `.env.preprod`, `.env.prod`, `.env.example` (template — document new env vars here). Each bot needs its own token: `RIDEBOT_TOKEN`, `STONESBOT_TOKEN`.
- `/metrics` (Prometheus) requires `Authorization: Bearer $METRICS_TOKEN` when the token is set.

### CI (`.github/workflows/`)

PRs to main/staging run pytest, Ruff, ty + `tsc --noEmit`, ESLint, an Alembic migration check, and a preprod Docker build. Merges to main build/push the multi-arch prod image; `portfolio/**` changes deploy to GitHub Pages. Pre-commit hooks (`.pre-commit-config.yaml`) run Ruff and ESLint.

---

## Git Guidelines

- **Never commit to main.** For each major change, create a branch named `<conventional-prefix>/<short-kebab-summary>` (e.g., `feat/xyz-dashboard`).
- Follow conventional commit format (`feat:`, `fix:`, `refactor:`).
- Keep the first line under 50 characters; use the imperative mood ("Add feature", not "Added feature").
- Do not include AI/Claude attribution in commit messages.

---

## Reliability & Safety Patterns

Lessons captured from an SRE audit. Apply these whenever writing new code.

### Startup

- **Validate required env vars at startup.** If a var is required for the app to function, check it immediately and call `sys.exit(1)` with a clear error message. Never let a missing var surface as a cryptic runtime error later.
- **Wrap startup sequences in try/except.** `startup()`, `load_extensions()`, and any other critical init calls must be wrapped so failures produce a clear log message before the process exits.
- **Validate `ADMIN_EMAILS` format before inserting.** Use a simple email regex and `sys.exit(1)` on any invalid entry — a malformed email in the DB can break auth flows.

### External HTTP calls

- **Always set an explicit timeout.** Every `httpx.AsyncClient` call must pass `timeout=10.0` (or a domain-appropriate value). Never use a client without a timeout — a stalled endpoint will hang the event loop indefinitely.
- **Never use synchronous `requests` in async code.** Use `httpx.AsyncClient` with `await` everywhere. A synchronous HTTP call blocks the entire asyncio event loop and freezes all bot responsiveness.

### Retry logic

- **Only retry transient errors.** Use `tenacity.retry_if_exception(predicate)` with a predicate that matches `httpx.TransportError`, `httpx.TimeoutException`, and rate-limit signals. Retrying on all `Exception` wastes time on auth errors, schema errors, and other permanent failures.

### LLM / external API response parsing

- **Never use hardcoded byte offsets to extract JSON.** Use `re.search` to locate fenced code blocks or fall back to `json.loads(content.strip())` directly. Hardcoded slices (`content[8:-3]`) silently produce garbage when the format changes.

### Caching

- **Update cache before committing, invalidate on failure.** When a DB write also updates an in-memory cache, set the cache value first, then commit. Wrap the DB calls in try/except and `cache.pop(key)` on exception so the next read re-fetches a fresh value rather than serving a stale one.
- **Cloudflare / external key caches need a TTL.** Global caches set once on first request and never refreshed will serve stale data after key rotation. Store a fetch timestamp and re-fetch when `time.time() - fetched_at > TTL`.

### Bot lifecycle

- **Wrap `bot.close()` with a timeout.** `await asyncio.wait_for(bot.close(), timeout=10.0)` prevents an unreachable Discord connection from blocking shutdown indefinitely and leaking DB connections.
- **Track failed extension loads.** Store failed extension names in a module-level set (e.g. `_failed_extensions`) so the health check and operators can see which cogs didn't load, rather than reporting the bot as healthy when commands are silently broken.

### Error reporting

- **Fall back to stderr when the bot is unavailable.** `send_error_to_discord()` must print to `sys.stderr` when `get_bot()` returns None — startup/shutdown failures are the most critical ones and must not be silently swallowed.
- **Handle missing error channels.** If `ERROR_CHANNEL_ID` references a deleted or unavailable channel, fall back to stderr rather than silently dropping the error.

### Auth & session middleware

- **DB errors in auth middleware must return 401, not 500.** Wrap the session DB query in try/except and return `Response("Unauthorized", status_code=401)` on failure. A 500 from the auth layer confuses the frontend and bypasses the login redirect.

### Database

- **Back up SQLite before migrations.** `entrypoint.sh` copies the DB to a timestamped sibling file before running `alembic upgrade head`. A failed migration against a live DB without a backup has no recovery path.
- **Use `pool_pre_ping=True` and `pool_recycle`** when creating the async engine so stale connections after a DB restart are recycled rather than handed to the next request.

### Frontend — data fetching

- **Do not set `refetchOnReconnect: false`** on queries where eventual consistency matters. The query will never recover after a network interruption, leaving users with permanently stale data. Only disable it when you have an explicit reason (e.g. a mutation-driven cache invalidation strategy).
- **SSE `EventSource` must have an `onerror` handler.** Without one, stream failures are silent — the user sees stale data indefinitely. Set an error state and close the stream in `es.onerror`.
- **Always set an `error` state in geometry/data fetch hooks.** When a `catch` block only logs to console, the component renders in a broken-looking state with no explanation. Surface a visible fallback via an `error` state returned from the hook.

### Frontend — error isolation

- **Wrap each lazy-loaded admin component in its own `<ErrorBoundary>`+`<Suspense>` pair.** A single shared `<Suspense>` with no `ErrorBoundary` means one failing component crashes the entire admin section. Use the inline `fallback` prop on `ErrorBoundary` for contained section-level errors.
- **Use `<Navigate replace>` instead of `useEffect`+`navigate()` for auth redirects.** The `useEffect` approach has a frame where the component returns `null` (blank screen). If the component unmounts before the effect fires, the user is stuck.

### Ops / deployment

- **Restrict sensitive observability endpoints.** `/metrics` exposes request rates and error counts useful for reconnaissance. When `METRICS_TOKEN` is set, the guard middleware requires `Authorization: Bearer <token>`. Keep the env var documented in `.env.example`.
- **Use a temp file inside the repo directory, not `/tmp`.** OS temp-dir clearing mid-script silently corrupts deploys. Use `$SCRIPT_DIR/.gitkeep.tmp` or similar repo-relative paths for any transient files in deploy scripts.
