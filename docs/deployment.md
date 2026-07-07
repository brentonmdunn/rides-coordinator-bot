# Deployment

## Overview

The backend (Discord bot + FastAPI) and the compiled frontend are bundled together into a single Docker image. The image is served as a single container that handles both the bot connection and the web dashboard.

See [CI_CD.md](CI_CD.md) for the image promotion strategy (build on PR, promote on merge).

---

## Docker images

| Registry | Image | Description |
|----------|-------|-------------|
| Docker Hub | `brentonmdunn/ride-bot-preprod:latest` | Built on each PR targeting `main` |
| Docker Hub | `brentonmdunn/ride-bot:latest` | Promoted from preprod on merge to `main` |

Multi-platform builds (`linux/amd64`, `linux/arm64`) run via GitHub Actions.

---

## Build locally

From `backend/`:

```bash
# Full production build (frontend + backend bundled)
bash build-and-export.sh
```

Or with Docker directly:

```bash
docker build -f backend/Dockerfile -t ride-bot .
```

The Dockerfile:
1. Builds the React frontend (`npm run build`).
2. Copies the built files into `backend/admin_ui/`.
3. Installs Python dependencies with `uv`.
4. Sets the entrypoint to `entrypoint.sh`, which runs Alembic migrations then starts the bot.

---

## Entrypoint

`backend/entrypoint.sh` runs on container start:

1. `alembic upgrade head` — applies any pending migrations.
2. `python main.py` — starts the bot + FastAPI server.

The API is served by `uvicorn` and listens on port `8000` by default.

---

## Required environment variables (production)

```bash
APP_ENV=prod
DISCORD_BOT_TOKEN=...
DATABASE_URL=sqlite+aiosqlite:///./db/rides.db
ADMIN_EMAILS=you@example.com

# Auth
AUTH_PROVIDER=self
DISCORD_OAUTH_CLIENT_ID=...
DISCORD_OAUTH_CLIENT_SECRET=...
DISCORD_OAUTH_REDIRECT_URI=https://yourdomain/api/auth/discord/callback
FRONTEND_BASE_URL=https://yourdomain

# AI grouping
GOOGLE_API_KEY=...

# Optional
GOOGLE_CALENDAR_ID=...
DISCORD_GUILD_ID=...
DISCORD_RIDE_COORDINATOR_ROLE_ID=...
REDIS_URL=redis://redis:6379
MAIN_RIDES_COORD_USER_ID=...
```

---

## Frontend deployment

The frontend is served as static files from `backend/admin_ui/` by the FastAPI app. They are bundled into the Docker image at build time.

To deploy a frontend-only update without a full backend rebuild:

```bash
bash deploy-frontend.sh
```

This script builds the frontend and copies the output to the appropriate location on the server.

---

## Database persistence

The SQLite database file (`backend/db/rides.db`) must be mounted as a persistent volume. If the container is replaced without preserving this volume, all data is lost.

Example Docker run:

```bash
docker run -d \
  --env-file .env.prod \
  -v /data/rides:/app/backend/db \
  -p 8000:8000 \
  brentonmdunn/ride-bot:latest
```

---

## Pre-production image

A preprod-specific Dockerfile (`backend/Dockerfile.preprod`) exists for testing changes in a staging environment before promoting to production.

---

## Updating production

The standard flow:

1. Open a PR against `main`.
2. CI builds and pushes to `brentonmdunn/ride-bot-preprod`.
3. Merge the PR.
4. CI promotes the preprod image to `brentonmdunn/ride-bot`.
5. Pull the new image on your server and restart the container.

> **Warning:** Pushing directly to `main` will promote the previous preprod image — not your latest changes. Always use Pull Requests. See [CI_CD.md](CI_CD.md) for details.

---

## Migrating to a new VM

The entire application state lives in one SQLite file (`backend/db/bot.db`). To move to a new
host, export the database on the old VM and import it on the new one. The export uses SQLite's
online backup API, so it produces a consistent snapshot **even while the bot is running**.

All scripts run from `backend/` with `uv`.

### 1. Export on the old VM

```bash
uv run python scripts/db_export.py
# → bot-db-backup-<timestamp>.db   (or .db.enc if encryption is enabled)
```

**Encryption (optional but recommended if the file leaves a trusted channel):**

```bash
uv run python scripts/db_export.py --gen-key   # prints a Fernet key — save it
export BACKUP_ENCRYPTION_KEY=<that key>
uv run python scripts/db_export.py             # now produces an encrypted .db.enc
```

If `BACKUP_ENCRYPTION_KEY` is unset, the export is unencrypted and the script prints a loud
warning. The backup contains user emails, names, and Discord identities — only move an
unencrypted file over a trusted channel (e.g. `scp` over SSH) and delete it afterward.

### 2. Copy to the new VM

```bash
scp bot-db-backup-<timestamp>.db <user>@<new-vm>:/path/to/repo/backend/
```

### 3. Import on the new VM

> **Stop the app/container first** — there must be no open writers on the target database.

```bash
# If the backup is encrypted, set the same key first:
export BACKUP_ENCRYPTION_KEY=<the key from step 1>

uv run python scripts/db_import.py --input bot-db-backup-<timestamp>.db --force
```

The import auto-detects encrypted vs. plain backups, validates the file with
`PRAGMA integrity_check`, and **backs up any existing database** (timestamped) before swapping
the new one in. On the next startup, `entrypoint.sh` runs `alembic upgrade head`, so a backup
taken from an older schema is migrated forward automatically.

After importing, start the container as usual. Existing login sessions are environment-bound, so
users may need to log in again.
