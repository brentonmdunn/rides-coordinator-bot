# Database Schema

The backend uses SQLite via SQLAlchemy (async) with Alembic for migrations. The database file lives at `backend/db/rides.db`.

Models are defined in `backend/bot/core/models.py`. All migrations are in `backend/alembic/versions/`.

---

## Tables

### `discord_usernames`

Maps Discord usernames to real names. Populated by the CSV/Google Sheets sync.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `discord_username` | str | |
| `first_name` | str | |
| `last_name` | str | |

---

### `locations`

Stores user location and ride preferences. Populated by the CSV sync.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `name` | str | Full name |
| `discord_username` | str? | |
| `year` | str? | Class year |
| `location` | str? | Pickup location label |
| `driver` | str? | Driver availability (`Yes`, `If necessary`, `No`) |

---

### `non_discord_rides`

Manually added pickup entries for people without Discord accounts.

| Column | Type | Notes |
|--------|------|-------|
| `name` | str PK | |
| `date` | date PK | |
| `location` | str? | Pickup location |
| `emoji` | str? | Emoji associated with the location |

Composite primary key on `(name, date)` — one entry per person per date.

---

### `ride_coverage`

Tracks which Discord users have been assigned a ride (i.e., appear in a grouping message).

| Column | Type | Notes |
|--------|------|-------|
| `discord_username` | str PK | |
| `message_id` | str PK | The grouping message where they were assigned |
| `datetime_detected` | datetime | Set on insert (server default) |

Composite primary key on `(discord_username, message_id)`. Entries are scanned from messages containing `"drive:"` in the rides announcements channel.

---

### `event_threads`

Tracks which Discord thread IDs have the "auto-add reactors" feature enabled.

| Column | Type | Notes |
|--------|------|-------|
| `message_id` | str PK | Discord thread ID (string) |

---

### `message_schedule_pauses`

Stores pause state for each ask-rides scheduled job.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `job_name` | enum | `friday`, `sunday`, or `sunday_class` (unique) |
| `is_paused` | bool | |
| `resume_after_date` | date? | Event date after which job auto-resumes |
| `updated_at` | datetime | Auto-updated on write |

---

### `feature_flags`

Feature toggles for bot behavior and scheduled jobs.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `feature` | str (unique) | Flag name, e.g. `bot`, `ask_friday_rides_job` |
| `enabled` | bool | |

See `FeatureFlagNames` enum in `bot/core/enums.py` for all valid flag names, and [feature-flags.md](feature-flags.md) for descriptions.

---

### `user_accounts`

User accounts for dashboard access. Invite-only when `AUTH_PROVIDER=self`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `email` | str? (unique) | Populated on first Discord login |
| `role` | enum | `viewer`, `ride_coordinator`, `admin` |
| `role_edited_by` | str? | Email of admin who last changed the role |
| `discord_user_id` | str? (unique) | Set on first Discord login; used for subsequent logins |
| `discord_username` | str? | Set on invite or first login |
| `invited_by` | str? | Email of admin who created the invite |
| `invited_at` | datetime? | |
| `created_at` | datetime | Server default |
| `updated_at` | datetime | Auto-updated |

---

### `auth_sessions`

Server-side session storage for the self-hosted OAuth provider.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `session_id_hash` | str (unique) | SHA-256 of the random token stored in the cookie |
| `email` | str | |
| `csrf_token` | str | Readable cookie value for CSRF protection |
| `created_at` | datetime | |
| `last_activity_at` | datetime | Updated on each (non-throttled) request |
| `expires_at` | datetime | 30-day sliding window |

---

### `user_preferences`

Per-user UI preferences. Keyed by email.

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `id` | int PK | | |
| `email` | str (unique) | | Matches `user_accounts.email` |
| `show_map_labels` | bool | `true` | Whether to show location labels on the map |
| `created_at` | datetime | | |
| `updated_at` | datetime | | Auto-updated |

---

### `ride_reaction_events`

Audit log of every reaction add/remove on ride announcement messages.

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `message_id` | str | Discord message ID |
| `discord_username` | str | |
| `display_name` | str? | |
| `emoji` | str | Emoji string |
| `action` | str | `add` or `remove` |
| `occurred_at` | datetime | Server default |
| `ride_date` | date? | Parsed event date for the ride |
| `ride_type` | str? | `friday`, `sunday`, `sunday_class`, or `wednesday` |

---

## Migrations

| Command | Description |
|---------|-------------|
| `uv run alembic upgrade head` | Apply all pending migrations |
| `uv run alembic revision --autogenerate -m "desc"` | Create a new migration from model changes |
| `uv run alembic downgrade -1` | Roll back the last migration |
| `uv run alembic history` | Show migration history |

Migration files live in `backend/alembic/versions/`. Never edit an applied migration — always create a new one.
