# Ride Coverage

Ride coverage tracks which users who reacted to a ride announcement have been assigned to a driver. It surfaces as a widget on the dashboard and is driven by real-time Discord message listeners.

---

## How it works

When a coordinator posts a **grouping message** — any message in the rides-announcements channel that contains `drive:` followed by `@mentions` — the bot reads the mentioned users and records them as "covered" in the database. The dashboard widget then compares that list against whoever reacted to the original ask-rides message to show who still needs a ride.

```
Coordinator posts: "drive: @Alice @Bob"
         │
         ▼
on_message / on_message_edit (cog)
         │  checks: is_in_any_coverage_message_lookup_window()
         ▼
RideCoverageRepository.add_coverage_entries()  ←  ride_coverage table
         │
         ▼
GET /api/check-pickups/{ride_type}
         │  RideCoverageService.get_coverage_summary()
         │  compares reacted users vs covered users
         ▼
Dashboard widget
```

---

## Time windows

All times are **America/Los_Angeles**.

### Widget visibility

The dashboard widget only renders during these windows. Outside them `is_in_visibility_window` is `false` and the widget is hidden.

| Ride type | Widget shows |
|-----------|-------------|
| Friday    | Friday 12:00 PM – Friday 11:59 PM |
| Sunday    | Saturday 4:00 PM – Sunday 1:00 PM |

### Message lookup window

Only grouping messages posted within these windows are recorded as coverage entries. Messages outside the window are silently skipped — both in real-time (`on_message`) and during a force sync.

| Ride type | Accepted message times |
|-----------|----------------------|
| Friday    | Friday 12:00 PM – Friday 7:30 PM |
| Sunday    | Saturday 3:00 PM – Sunday 10:30 AM |

The DB query in `get_coverage_summary` also uses the start of this window as its `since` cutoff, so only entries from the current cycle are counted.

---

## Configuration

Windows are defined in `backend/bot/utils/time_helpers.py`:

| Constant | Controls |
|----------|----------|
| `COVERAGE_WIDGET_WINDOWS` | When `is_in_visibility_window` is `true` |
| `COVERAGE_MESSAGE_LOOKUP_WINDOWS` | Which messages are counted; DB query cutoff |

To adjust a window, edit the relevant `TimeWindow` in those dicts. `TimeWindow` supports `start_minute` / `end_minute` for sub-hour precision and allows `start_day == end_day` for same-day spans.

---

## Data model

**Table:** `ride_coverage`

| Column | Type | Notes |
|--------|------|-------|
| `id` | integer | Primary key |
| `discord_username` | text | Covered user's Discord username |
| `message_id` | text | Discord message ID of the grouping message |
| `datetime_detected` | datetime | When the entry was inserted |

---

## API

### `GET /api/check-pickups/{ride_type}`

Returns coverage status for `friday` or `sunday`.

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `users` | array | Each user who reacted, with `discord_username` and `has_ride` |
| `total` | int | Number of users who reacted to the ask-rides message |
| `assigned` | int | Number of those users who have been covered |
| `message_found` | bool | Whether the ask-rides reaction message was located |
| `has_coverage_entries` | bool | Whether any coverage entries exist in the lookup window |
| `is_in_visibility_window` | bool | Whether the widget should be shown right now |

### `POST /api/check-pickups/sync`

Force-rescans the rides-announcements channel history (back to last Sunday) and rebuilds coverage entries. Also removes entries for messages that no longer exist (deleted messages). Useful when the database is out of sync with Discord.

---

## Cog listeners

All live in `backend/bot/cogs/ride_coverage.py`.

### `on_ready`

Runs `sync_ride_coverage` once per bot session on startup to catch any grouping messages posted while the bot was offline.

### `on_message`

Fires on every new message. Short-circuits immediately if the current time is outside all coverage message lookup windows (`is_in_any_coverage_message_lookup_window()`). If inside a window and the message contains `drive:`, extracts the mentioned passengers and inserts coverage entries.

### `on_message_edit`

Checks whether the **original** message was posted within a lookup window (using `message.created_at`), allowing coordinators to edit grouping messages after the window has closed without losing the coverage data. Computes the diff of mentioned users between the before/after message and adds or removes entries accordingly.

### `on_message_delete`

Removes all coverage entries tied to a deleted message regardless of time window, keeping the database clean.

---

## Sync process

`RideCoverageService.sync_ride_coverage()` (triggered by `on_ready` or `POST /api/check-pickups/sync`):

1. Scans the rides-announcements channel for messages since last Sunday.
2. Skips bot messages and non-grouping messages (no `drive:`).
3. Skips messages whose `created_at` is outside all coverage message lookup windows.
4. Inserts coverage entries for any remaining grouping messages.
5. Queries the DB for all message IDs recorded since last Sunday and compares against the set found in Discord — deletes entries for any IDs that are no longer present (orphan cleanup).
