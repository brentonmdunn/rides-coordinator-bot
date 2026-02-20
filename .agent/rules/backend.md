---
trigger: always_on
---

# Backend Conventions

The backend is a Python 3.13 application in `backend/`. It runs a Discord bot (`discord.py`) and a FastAPI web API side by side.

## Architecture

- **Cogs** (`bot/cogs/`): Discord slash commands and event listeners. Each file is a cog that gets auto-loaded.
  - Disabled cogs go in `bot/cogs_disabled/`, testing cogs in `bot/cogs_testing/`.
- **Services** (`bot/services/`): Business logic layer. Cogs call services, never repositories directly.
- **Repositories** (`bot/repositories/`): Data access layer. All SQL/database queries live here.
- **Jobs** (`bot/jobs/`): Scheduled tasks run by APScheduler. Disabled jobs go in `bot/jobs_disabled/`.
- **API** (`api/`): FastAPI routes in `api/routes/`, auth in `api/auth.py`, middleware in `api/middleware/`.

## Key Patterns

- Use `async`/`await` everywhere — the DB uses aiosqlite + async SQLAlchemy.
- Never use hardcoded strings for enums — always use `bot/core/enums.py` (e.g., `JobName`, `FeatureFlagNames`, `DaysOfWeek`, `RideType`).
- Constants go in `bot/utils/constants.py` (bot-side) or `api/constants.py` (API-side).
- Logging goes through `bot/core/logger.py` — never use `print()`.
- Entry point is `backend/main.py`.
- The API entry point is `backend/run_api.py`.
