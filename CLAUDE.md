# CLAUDE.md

This file documents conventions and project-specific rules for AI coding assistants working in this repo.

---

## Tech Stack

This project contains both a Discord bot (Python) and a frontend web UI.

- **Discord bot**: Python (`discord.py`)
- **Backend API**: Python + FastAPI
- **Frontend**: React + Tailwind CSS v4
- **Database**: SQLite

### Tools

- Use `uv` to run Python or any Python-associated libraries (e.g., `uv run pytest`)
- Use **Ruff** for linting and formatting
- After modifying any Python code, always run:
  ```
  uv run invoke format
  uv run invoke lint
  ```

---

## Backend Conventions

The backend is a Python 3.13 application in `backend/`. It runs a Discord bot (`discord.py`) and a FastAPI web API side by side.

### Architecture

- **Cogs** (`bot/cogs/`): Discord slash commands and event listeners. Each file is a cog that gets auto-loaded.
  - Disabled cogs go in `bot/cogs_disabled/`, testing cogs in `bot/cogs_testing/`.
- **Services** (`bot/services/`): Business logic layer. Cogs call services, never repositories directly.
- **Repositories** (`bot/repositories/`): Data access layer. All SQL/database queries live here.
- **Jobs** (`bot/jobs/`): Scheduled tasks run by APScheduler. Disabled jobs go in `bot/jobs_disabled/`.
- **API** (`api/`): FastAPI routes in `api/routes/`, auth in `api/auth.py`, middleware in `api/middleware/`.

### Key Patterns

- Use `async`/`await` everywhere — the DB uses aiosqlite + async SQLAlchemy.
- Never use hardcoded strings for enums — always use `bot/core/enums.py` (e.g., `JobName`, `FeatureFlagNames`, `DaysOfWeek`, `RideType`).
- Constants go in `bot/utils/constants.py` (bot-side) or `api/constants.py` (API-side).
- Logging goes through `bot/core/logger.py` — never use `print()`.
- Entry point is `backend/main.py`.
- The API entry point is `backend/run_api.py`.

### Centralizing Shared Logic (No Duplication Between Cogs and API)

Cogs and API routes are both **thin entry points** — they handle input/output for their respective interfaces (Discord vs. HTTP) but must not contain business logic themselves.

If a piece of logic is needed by both a cog and an API route (or could be in the future), it **must** live in a service:

```
Cog  ──┐
        ├──▶  Service  ──▶  Repository  ──▶  DB
API  ──┘
```

**Rules:**
- Never duplicate logic between a cog and an API route — extract it into a service method.
- Cogs call services. API routes call services. Neither calls repositories directly.
- If you find yourself copy-pasting logic from a cog into a route (or vice versa), stop and put it in a service instead.

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
4. **3-tier identity matching** (in `bot/services/auth_service.py`):
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
- 30-day sliding expiry, throttled touch (max one DB write per 5 min per session).
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
| `bot/services/auth_service.py` | Identity matching cascade + session lifecycle |
| `bot/repositories/auth_sessions_repository.py` | `auth_sessions` table access |
| `frontend/src/components/AuthGuard.tsx` | Route guard — redirects to `/login` on 401 |
| `frontend/src/lib/auth.ts` | CSRF cookie helper + `logout()` |

---

## Database Conventions

### Stack

- **SQLite** via **aiosqlite** (async driver) + **SQLAlchemy** (async ORM).
- Database file stored in `backend/db/`.

### Migrations

- Managed by **Alembic** (config: `backend/alembic.ini`, migrations dir: `backend/alembic/`).
- Generate a new migration: `uv run alembic revision --autogenerate -m "description"`
- Apply migrations: `uv run alembic upgrade head`

### Data Access Pattern

- **Repositories** (`bot/repositories/`): All database queries go here. Each repository file focuses on one domain (e.g., `locations_repository.py`, `feature_flags_repository.py`).
- **Services** (`bot/services/`): Call repositories — never write raw SQL in cogs or services.
- Cogs and API routes should call services, not repositories directly.

### Repository Conventions

Three rules apply to every DB repository:

1. **`@staticmethod` only** — repositories hold no instance state, so all methods are static.
2. **`session: AsyncSession` as the first parameter** — every DB method accepts a session. Repositories never open their own sessions.
3. **Consistent naming** — file: `<domain>_repository.py`, class: `<Domain>Repository`.

The **service layer owns the unit-of-work**: services open sessions with `async with AsyncSessionLocal() as session:` and pass them into repository calls.

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

## Discord Bot Conventions

### Structure

- **Entry point**: `backend/main.py` — boots the bot, auto-loads cogs, starts scheduled jobs.
- **Cogs** (`bot/cogs/`): Each file is a cog with slash commands or event listeners. Auto-loaded on startup.
- **Disabled cogs** (`bot/cogs_disabled/`): Cogs that are temporarily turned off — move files here to disable.
- **Testing cogs** (`bot/cogs_testing/`): Cogs used only during development.
- **Jobs** (`bot/jobs/`): Scheduled tasks using APScheduler (e.g., asking for rides on specific days).
- **Disabled jobs** (`bot/jobs_disabled/`): Move job files here to disable.

### Enums (Single Source of Truth)

All enums are in `bot/core/enums.py`. Key enums:

- `ChannelIds` / `RoleIds` / `CategoryIds` — Discord resource IDs
- `FeatureFlagNames` — feature flag identifiers
- `JobName` — scheduled job identifiers
- `DaysOfWeek` / `DaysOfWeekNumber` — day representations
- `PickupLocations` / `CampusLivingLocations` — ride locations
- `RideType` / `AskRidesMessage` — ride-related message types

### Feature Flags

- Managed via `FeatureFlagNames` enum and `feature_flags_repository.py`.
- Local development auto-disables jobs and message flags to prevent spam (see `disable_features_for_local_env()` in `main.py`).

---

## Logging Conventions

### Setup

- Logging is configured in `bot/core/logger.py`. It sets up the root logger with console + rotating file handlers.
- Every file uses its own per-module logger:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- **Never** use `from bot.core.logger import logger` — that's the root logger. Always create a per-module logger with `getLogger(__name__)`.
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
- **Never silently swallow exceptions.** If an `except` block returns a default value, still log the exception:
  ```python
  except Exception:
      logger.exception("Failed to check coverage status")
      return False
  ```

### Transaction IDs & Context

- Slash commands: wrap with `@log_cmd` (from `bot.core.logger`) to auto-assign a transaction ID and log the command invocation.
- Scheduled jobs: wrap with `@log_job` to auto-assign a transaction ID.
- API requests: transaction IDs are injected via `api/middleware/access_logger.py`.
- Log format includes `[txn:%(txn_id)s]` and `[%(user_email)s]` for tracing.

### Log Format

```
%(asctime)s %(levelname)-8s [txn:%(txn_id)s] [%(name)s:%(lineno)d] [%(user_email)s] %(message)s
```

- `%(name)s` shows the full module path (e.g., `bot.services.locations_service`), so there's no need to prefix messages with the module name manually.

### Common Patterns

- **Cog/command entry points**: Log at `INFO` with user-relevant context (command name, arguments, day, message_id).
- **Service operations**: Log start/completion at `INFO`; intermediate steps at `DEBUG`.
- **Repository queries**: Generally no logging needed for routine queries. Log exceptions and unusual conditions.
- **Bot not ready / missing optional config**: Use `WARNING`, not `ERROR`.
- **Sending errors to Discord**: Always pair `logger.exception(...)` with `await send_error_to_discord(...)` for unexpected errors in user-facing flows.

---

## Frontend Conventions

The frontend is a React 19 SPA in `frontend/`, built with Vite and Tailwind CSS v4.

### Architecture

- **Components** (`src/components/`): Reusable UI components. Uses shadcn/ui (`components.json` present).
- **Pages** (`src/pages/`): Top-level page components.
- **Types** (`src/types.ts`): Shared TypeScript type definitions.
- **Utilities** (`src/lib/utils.ts`): Shared helper functions (e.g., `getAutomaticDay`, `useCopyToClipboard`).

### Key Libraries

- **@tanstack/react-query**: Server state management and data fetching.
- **react-router-dom**: Client-side routing.
- **@dnd-kit**: Drag-and-drop functionality.
- **lucide-react**: Icon library.
- **class-variance-authority** + **clsx** + **tailwind-merge**: Conditional styling utilities (shadcn pattern).

### Standards

- Use TypeScript — no `any` types.
- Run `npm run lint` (ESLint) before committing frontend changes.
- Environment configs: `.env.development` (local) and `.env.production`.
- Build with `npm run build` (`tsc -b && vite build`).

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

## Docker & Deployment

### Docker

- Main Dockerfile: `backend/Dockerfile`
- Preprod Dockerfile: `backend/Dockerfile.preprod`
- Image: `brentonmdunn/ride-bot`
- CI/CD builds multi-platform images on merge to `main` (see `.github/workflows/`).

### Environment Configs

All in `backend/`:

- `.env.dev` — Local development
- `.env.preprod` — Pre-production
- `.env.prod` — Production
- `.env.example` — Template for new setups

### Frontend Deployment

- Deploy script: `deploy-frontend.sh` (root of repo)
- Build output: `frontend/dist/`

### CI/CD

- Workflows are in `.github/workflows/`.
- Docker startup test runs on PRs to validate the image builds and starts correctly.

---

## Testing Conventions

### Backend (Python)

- Tests live in `backend/tests/`, split into `unit/` and `integration/` directories.
- Run tests: `uv run pytest` (from `backend/`).
- Use `pytest-asyncio` for async test functions.
- Use `pytest-cov` for coverage reporting.

### Available Invoke Tasks

All run from `backend/` with `uv run invoke <task>`:

- `uv run invoke lint` — Run Ruff linter
- `uv run invoke format` — Format code with Ruff
- `uv run invoke fix` — Autofix lint errors
- `uv run invoke all` — Run lint + fix + format
- `uv run invoke test` — Run pytest
- `uv run invoke clean` — Remove dev commands

### Frontend (TypeScript)

- Run linter: `npm run lint` (from `frontend/`).

### Before Committing

- Always run `uv run invoke format` and `uv run invoke lint` after modifying Python code.
- Always run `uv run ty check` after modifying Python code.
- Always run `npm run lint` after modifying frontend code.
- Always run `npx tsc --noEmit` after modifying frontend code.
- You do not need to ask before running these commands and fixing code based on the output.

## Development
Never commits to main branch. For each major change, create a new branch with conventional commit prefix then a snake case short summary. For example, feat/xyz-dashboard.

When making commits, use conventional commits. Do not give attritubtion to Claude.

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