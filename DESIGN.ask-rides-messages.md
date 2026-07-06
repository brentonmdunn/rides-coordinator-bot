# Design: Editable Ask-Rides Messages

Admins site users (ride coordinators and above) can edit the title, body, and embed
color of the four ask-rides messages the bot sends. Edits are stored in the database,
fall back to the current hardcoded messages when no saved row (or no table) exists,
and propagate live to every open admin session via SSE.

---

## Requirements

| Requirement | Decision |
|---|---|
| Editable fields | Embed **title** and **body** (template with placeholders), plus **embed color** chosen from a preset list |
| Defaults | The current hardcoded title/body/color are pre-filled as the starting value; if the DB table or row is missing, the bot silently uses these defaults |
| Permissions | `require_ride_coordinator` (same tier as send-now and pause controls) |
| Propagation | SSE push — every user viewing the admin site sees an edit within ~1s |
| Coverage | All four message types: Wednesday fellowship, Friday fellowship, Sunday service, Sunday class |

---

## Current state (for reference)

- Message bodies are built in `backend/bot/jobs/ask_rides.py:108-150` (`_make_wednesday_msg`, `_make_friday_msg`, `_make_sunday_service_msg`, `_make_sunday_class_msg`).
- Dynamic parts interpolated at send time: next event date (`get_next_date_str`) and, for Sunday service, a coordinator mention (`ping_user`).
- Embed title + color come from `RIDE_TYPES_CONFIG` (`ask_rides.py:158-175`), matched by keywords in the message text.
- `AskRidesMessage` enum (`bot/core/enums.py:159-165`) covers Friday/Sunday-service/Sunday-class but **not Wednesday**.

## Template placeholders

Stored bodies/titles are Python-`str.format`-style templates. Supported tokens:

| Token | Meaning | Available in |
|---|---|---|
| `{date}` | Next event date string (e.g. "7/9") | all types |
| `{ping}` | Main rides coordinator mention — resolved from the `main_rides_coordinator_user_id` global setting (see below), **not** an env var | Sunday service only |

Rendering uses `format_map` with a defaulting dict so an unknown token never raises at
send time. The PUT endpoint validates that only supported tokens appear, so bad
templates are rejected at save time, not at 11am on Monday.

## Preset colors

A fixed palette (enum → `discord.Color`), stored by key:

`teal`, `green`, `blue`, `blurple`, `pink`, `magenta`, `orange`, `yellow`, `red`, `purple`

Defaults per message type match today's colors (Wednesday: teal, Friday: pink,
Sunday service: blue, Sunday class: blurple).

---

## Backend plan

### 1. Enum (`bot/core/enums.py`)

- New `AskRidesMessageType(StrEnum)`: `WEDNESDAY_FELLOWSHIP`, `FRIDAY_FELLOWSHIP`,
  `SUNDAY_SERVICE`, `SUNDAY_CLASS`. (A new enum rather than extending
  `AskRidesMessage`, whose string values are matched against message text elsewhere.)
- New `EmbedColorChoice(StrEnum)` for the preset palette, with a mapping to
  `discord.Color` in `bot/utils/constants.py`.

### 2. Model + migration

New table in `bot/core/models.py`:

```python
class AskRidesMessageTemplate(Base):
    __tablename__ = "ask_rides_message_templates"

    message_type: Mapped[str] = mapped_column(primary_key=True)  # AskRidesMessageType
    title: Mapped[str]
    body: Mapped[str]
    color: Mapped[str]          # EmbedColorChoice key
    updated_by: Mapped[str]     # email of last editor
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
```

Alembic migration via `uv run alembic revision --autogenerate -m "add ask_rides_message_templates"`.
Rows are created lazily on first save — no seed data needed, since absence ⇒ default.

### 3. Defaults live in code

`bot/jobs/ask_rides.py` (or a small `bot/utils/ask_rides_defaults.py`) exports
`DEFAULT_TEMPLATES: dict[AskRidesMessageType, MessageTemplate]` containing the exact
current title/body/color, with `{date}` / `{ping}` tokens replacing today's inline
interpolation. This single dict is the fallback source **and** what the API returns
as the pristine/default state.

### 4. Repository (`bot/repositories/ask_rides_messages_repository.py`)

Standard DB repo conventions (`@staticmethod`, `session` first param):

- `get_all(session) -> list[AskRidesMessageTemplate]`
- `get(session, message_type) -> AskRidesMessageTemplate | None`
- `upsert(session, message_type, title, body, color, updated_by)`
- `delete(session, message_type)` — used by "reset to default"

### 5. Service (`bot/services/ask_rides_messages_service.py`)

Owns the unit of work and the **fallback logic**:

- `get_effective_templates() -> dict[AskRidesMessageType, EffectiveTemplate]` —
  merges DB rows over `DEFAULT_TEMPLATES`; each entry carries `is_customized`.
- `get_effective_template(message_type)` — same for one type; **wraps the DB query in
  try/except** — on `OperationalError` (table missing) or any DB failure it
  `logger.exception(...)`s and returns the default. The scheduled job must never fail
  to send because of this feature.
- `update_template(message_type, title, body, color, updated_by)` — validates
  placeholders + color, upserts, then publishes an SSE event.
- `reset_template(message_type)` — deletes the row, publishes an SSE event.
- `render(template, message_type) -> tuple[title, body]` — fills `{date}` (and
  `{ping}` for Sunday service) via `format_map` with safe defaults.

### 6. Job changes (`bot/jobs/ask_rides.py`)

Each `_make_*_msg` / `_ask_rides_template` path calls
`AskRidesMessagesService.get_effective_template(...)` and renders it, instead of the
inline f-strings. Embed title and color come from the effective template rather than
`RIDE_TYPES_CONFIG` keyword matching. Emoji reactions, channel, `@Rides` ping, and
calendar-conditional sending are unchanged.

### 7. API routes (in `api/routes/ask_rides.py`)

| Route | Auth | Behavior |
|---|---|---|
| `GET /api/ask-rides/messages` | `require_ride_coordinator` | All four effective templates + `is_customized`, `default` (for the reset preview), allowed colors, allowed placeholders per type |
| `PUT /api/ask-rides/messages/{message_type}` | `require_ride_coordinator` | Pydantic-validated update: non-empty title/body, length caps (title ≤ 256, body ≤ 4096 per Discord embed limits), only-known placeholders, color in palette. Returns the updated effective template |
| `DELETE /api/ask-rides/messages/{message_type}` | `require_ride_coordinator` | Reset to default |
| `GET /api/ask-rides/messages/stream` | session auth (same as reaction-log stream) | SSE stream for live propagation |

### 8. SSE propagation

Mirror `reaction_log_stream.py`: a module-level `messages_broadcaster`
(subscribe → `asyncio.Queue`, 30s heartbeat). `update_template` / `reset_template`
publish `{"type": "templates_updated", "message_type": ...}`. Clients don't trust the
event payload for data — they just invalidate the react-query cache and refetch.

---

## Main rides coordinator as a global setting

Today the `{ping}` mention in the Sunday service message resolves from the
`MAIN_RIDES_COORD_USER_ID` env var (`bot/jobs/ask_rides.py:139`). This moves into the
existing `global_settings` table (key: `main_rides_coordinator_user_id`) so it is
editable from the admin site. **There is no env-var fallback** — the env var will be
deleted; the DB value is the only source.

### Storage & API

- Reuses `GlobalSettingsRepository` (same pattern as `fellowship_season`), fronted by
  a small service method with the same table-missing/DB-error safety as the templates.
- `GET /api/ask-rides/coordinator` (`require_ride_coordinator`) — returns the stored
  ID plus, when the bot is ready, the resolved Discord username/display name so the UI
  can show *who* will be pinged, not just a number.
- `PUT /api/ask-rides/coordinator` (`require_ride_coordinator`) — save-time
  validation: value must be all digits, 17–20 chars (Discord snowflake shape). If the
  bot is ready, also resolve it via `bot.fetch_user()`:
  - user found → save, return the username for confirmation;
  - user not found → **reject with 422** ("no Discord user with this ID");
  - bot not ready / Discord API error → save anyway but return a `warning` field
    ("could not verify this ID right now") — Discord being down shouldn't block a save.
- Frontend: a small "Main rides coordinator" field in the MessageTemplatesEditor
  section (input + resolved-name chip + save), invalidated by the same SSE stream.

### Send-time resolution

`render()` for Sunday service reads the setting inside the same try/except as the
template fetch. If the value is missing, non-numeric, or the DB read fails, `{ping}`
renders as the literal fallback text **"the rides coordinators"** and a `WARNING` is
logged (plus `send_error_to_discord`) — the message always sends.

### Failure conditions (brainstorm)

| # | Failure | When it bites | Behavior / mitigation |
|---|---|---|---|
| 1 | Setting was never created (fresh DB, or env var deleted before anyone saved a value in the UI) | First Sunday send after cutover | `{ping}` → "the rides coordinators" fallback text, `WARNING` logged, error surfaced to the Discord error channel; admin UI shows an amber "not configured" banner on load |
| 2 | `global_settings` table missing (migration not run) | Send time + GET route | Same fallback as #1; GET returns `configured: false` instead of 500 |
| 3 | DB unreachable at send time | Send time | Whole-template fallback already covers this — defaults + fallback ping text; job never crashes |
| 4 | Value is garbage (non-numeric, empty string, truncated paste) | Save time | Rejected by PUT validation (digits, 17–20 chars); can only reach the DB via manual SQL — runtime guard in `render()` still catches it |
| 5 | Valid snowflake but no such Discord user (typo'd ID, deleted account) | Save time / send time | Caught at save when the bot is up (422). If it slips through (bot was down at save, or account deleted later), Discord renders a broken mention — cosmetic only; the resolved-name chip in the UI makes staleness visible next time anyone looks |
| 6 | Right shape, wrong person (someone pastes a message ID or another member's ID) | Human error | Resolved-username confirmation at save is the guard — the editor sees the actual name before/after saving |
| 7 | Coordinator leaves the server (ID still a real Discord user) | Send time | Mention renders but doesn't notify a server member; not detectable at save via `fetch_user` — optionally check guild membership (`guild.get_member`) at save and warn (not reject, since the bot may share multiple guilds) |
| 8 | Bot not ready when PUT arrives (API up before gateway connect) | Save time | Save succeeds with a "could not verify" warning rather than blocking — availability over strictness |
| 9 | Discord API outage during save-time verification | Save time | Same as #8 — verification is best-effort, never a hard dependency |
| 10 | Concurrent edits from two admins | Save time | Last-write-wins on a single key; SSE invalidation refreshes the other viewer within ~1s, same as templates |
| 11 | Stale cache after an edit | Between edit and next send | Don't cache this setting (it's read once per send, not per request) — read fresh from DB at send time |
| 12 | Old env var still set after cutover | Post-deploy confusion | Code no longer reads it anywhere (grep-verified at implementation time); note removal in `.env.example` so nobody re-adds it |
| 13 | Someone saves the **bot's own** user ID | Human error | Save-time check: reject IDs matching `bot.user.id` (422) |

### Migration/cutover note

There is deliberately **no automatic seed from the env var** (it may already be
deleted). After deploy, the admin UI shows the "not configured" banner until a
coordinator saves a value; until then Sunday sends use the fallback text. This is a
one-time, self-healing gap.

---

## Frontend plan

New component group `frontend/src/components/AskRidesDashboard/MessageTemplatesEditor.tsx`,
surfaced as a section/tab of the existing AskRidesDashboard.

- **Query**: `useQuery({ queryKey: ['askRidesMessages'], queryFn: apiFetch('/api/ask-rides/messages') })`.
- **Per message type card**:
  - Title input + body textarea, pre-filled with the effective template.
  - Color picker: row of preset swatches (keys from the API response).
  - Live preview styled like a Discord embed (color bar, title, body) with `{date}`
    substituted by the real next event date (already available from the upcoming-dates
    endpoint) and `{ping}` shown as a mention chip.
  - "Customized" badge when `is_customized`; **Reset to default** button (amber, per
    existing revert-button convention) that calls the DELETE route after a confirm.
  - Save button → `useMutation` PUT → `invalidateQueries(['askRidesMessages'])`.
- **Live updates**: `useEffect` opening `EventSource('/api/ask-rides/messages/stream', { withCredentials: true })`;
  `onmessage` → `queryClient.invalidateQueries({ queryKey: ['askRidesMessages'] })`;
  `onerror` → set error state and close (per repo SSE conventions).
  - If another user saves while you have unsaved local edits, show a non-destructive
    banner ("This message was just updated by someone else — refresh to see it")
    rather than clobbering the in-progress edit.
- Styling uses OKLCH semantic tokens only (`bg-card`, `text-muted-foreground`, etc.).

---

## Testing

- **Unit — service**: default fallback when row missing; fallback + `logger.exception`
  when table missing (simulate `OperationalError`); merge of DB row over default;
  placeholder validation rejects unknown tokens; `render` fills `{date}`/`{ping}` and
  never raises on a stray token.
- **Unit — routes**: 403 for viewer role; PUT validation errors (empty body, bad
  color, unknown placeholder, over-length title); PUT→GET round trip; DELETE resets
  `is_customized`.
- **Unit — coordinator setting**: PUT rejects non-snowflake values and the bot's own
  ID; unverifiable saves succeed with a warning; `render` falls back to "the rides
  coordinators" when the setting is missing, malformed, or the DB read fails.
- **Unit — job**: message construction uses the customized template when present and the
  default otherwise (extend `tests/unit/test_ask_rides.py`).
- **Frontend**: lint + `npx tsc --noEmit`; component test for the editor mirroring
  `season-toggle.test.tsx`.

## Rollout / order of work

1. Enum + model + Alembic migration.
2. Defaults dict + repository + service (with fallback) + unit tests.
3. Wire the job to the service (behavior is identical until someone saves an edit —
   safe to ship independently).
4. API routes + SSE broadcaster + tests.
5. Frontend editor + SSE hook.
6. `uv run invoke format && uv run invoke lint && uv run ty check`, `npm run lint`,
   `npx tsc --noEmit`, `uv run pytest`.

## Open edge cases handled

- **Table doesn't exist** (fresh DB, migration not yet run): service catches the DB
  error and returns defaults — both the job and the GET route keep working.
- **Send-time safety**: templates are validated at save; rendering uses
  `format_map` with defaults so even a bad stored value can't crash the scheduled job.
- **Concurrent editors**: SSE invalidation refreshes viewers; unsaved-edit banner
  avoids silent clobbering (last-write-wins on the server, which is acceptable here).
