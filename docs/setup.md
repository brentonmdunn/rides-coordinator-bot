# Local Development Setup

## Prerequisites

- Python 3.13+ (managed via `uv`)
- Node.js 20+
- A Discord bot token and application

## Backend

### 1. Install dependencies

From `backend/`:

```bash
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env.dev` and fill in the values. The minimum set needed to start the backend locally:

```bash
APP_ENV=local
DISCORD_BOT_TOKEN=your_token_here
DATABASE_URL=sqlite+aiosqlite:///./db/rides.db
```

With `APP_ENV=local`, all API requests are automatically authenticated as `dev@example.com` — no Discord OAuth round-trip is needed. Set `ADMIN_EMAILS=dev@example.com` to give that account admin access.

See [Environment Variables](#environment-variables) for the full reference.

### 3. Initialize the database

From `backend/`:

```bash
uv run alembic upgrade head
```

### 4. Run the backend

The bot and API run as a single process:

```bash
uv run python main.py
```

The API listens on `http://localhost:8000` by default.

To run the API standalone (without the Discord bot):

```bash
uv run python run_api.py
```

---

## Frontend

From `frontend/`:

```bash
npm install
npm run dev
```

The dev server starts on `http://localhost:5173` and proxies API calls to `http://localhost:8000` (configured in `.env.development`).

---

## Running tests

From `backend/`:

```bash
uv run pytest
# or with coverage:
uv run pytest --cov
```

---

## Linting, formatting & type checking

Always run these after modifying Python:

```bash
uv run invoke format
uv run invoke lint
uv run ty check
```

Or use the combined invoke task:

```bash
uv run invoke typecheck
```

After modifying frontend:

```bash
npm run lint
npx tsc --noEmit
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `local` | Runtime environment: `local`, `preprod`, `prod`. `local` bypasses auth. |
| `AUTH_PROVIDER` | `cloudflare` | Auth provider: `cloudflare` (Cloudflare Access) or `self` (Discord OAuth). |
| `DISCORD_BOT_TOKEN` | — | Required. Discord bot token. |
| `DATABASE_URL` | — | SQLAlchemy async URL, e.g. `sqlite+aiosqlite:///./db/rides.db`. |
| `ADMIN_EMAILS` | — | Comma-separated emails to seed as admins on startup. |
| `FRONTEND_BASE_URL` | — | Base URL for redirect after OAuth login (e.g. `https://yourdomain`). |
| `AUTH_PROVIDER=self` vars | | Only needed when `AUTH_PROVIDER=self` |
| `DISCORD_OAUTH_CLIENT_ID` | — | Discord app client ID. |
| `DISCORD_OAUTH_CLIENT_SECRET` | — | Discord app client secret. |
| `DISCORD_OAUTH_REDIRECT_URI` | — | Must match redirect URI in Discord developer portal. |
| `DISCORD_GUILD_ID` | — | Optional. Enables auto-provisioning for users with the Ride Coordinator Discord role. |
| `DISCORD_RIDE_COORDINATOR_ROLE_ID` | — | Optional. The Discord role ID for auto-provisioning. |
| `LOCAL_USE_DISCORD_OAUTH` | `false` | Set to `true` to test real OAuth locally instead of the mock user. |
| `MAIN_RIDES_COORD_USER_ID` | — | Discord user ID of the main ride coordinator, mentioned in Sunday ride messages. |
| `GOOGLE_API_KEY` | — | Required for AI ride grouping (Gemini). |
| `GOOGLE_CALENDAR_ID` | — | Optional. Used to check for wildcard/special events before sending Sunday messages. |
| `REDIS_URL` | — | Optional. Redis URL for production caching (e.g. `redis://localhost:6379`). Falls back to in-memory cache when unset. |

---

## Testing real Discord OAuth locally

1. In the Discord developer portal, add `http://localhost:8000/api/auth/discord/callback` as a redirect URI.
2. Set these variables in your `.env.dev`:

```bash
AUTH_PROVIDER=self
LOCAL_USE_DISCORD_OAUTH=true
DISCORD_OAUTH_CLIENT_ID=...
DISCORD_OAUTH_CLIENT_SECRET=...
DISCORD_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/discord/callback
FRONTEND_BASE_URL=http://localhost:5173
ADMIN_EMAILS=your-discord-linked@email.com
```

3. Restart the backend and visit `http://localhost:5173/login`.

---

## Database migrations

Generate a migration after changing `bot/core/models.py`:

```bash
cd backend
uv run alembic revision --autogenerate -m "short description"
uv run alembic upgrade head
```

Never edit existing migration files after they have been applied.
