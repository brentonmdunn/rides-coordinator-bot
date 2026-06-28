# Job Scheduler

The bot uses APScheduler (via the `JobScheduler` cog) to run recurring tasks. All jobs run in the bot's async event loop and are started automatically on bot startup.

---

## Scheduled Jobs

### `run_ask_rides_all` — Wednesdays at noon PT

The main weekly job. Sends ride announcement messages to the rides announcements channel and driver availability messages to the driver chat channel.

**What it does:**

1. Sends a header ping to the @Rides role.
2. Sends the Friday fellowship ride request message (if enabled and not paused).
3. Sends the Sunday class ride request message (if enabled, not paused, and Sunday school is on the calendar).
4. Sends the Sunday service ride request message (if enabled, not paused, and no wildcard date on the calendar).
5. Warms the ask-rides message ID cache.
6. Sends Friday driver availability message to driver chat.
7. Sends Sunday driver availability message to driver chat.
8. Warms the driver message ID cache.

**Guards** — each sub-job independently checks:
- Its feature flag (e.g. `ask_friday_rides_job`).
- Whether the job is paused (via `message_schedule_pauses` table).
- For Sunday jobs: whether the master calendar (Google Calendar) shows a wildcard/skip event.
- Whether the date appears in the `WILDCARD_DATES` hardcoded list in `bot/jobs/ask_rides.py`.

**Triggering manually:** Use `POST /api/ask-rides/send-now` from the dashboard or API.

---

### `run_periodic_cache_warming` — every 30 minutes

Rotates through two reaction namespaces and warms the cache for each on alternating runs:

- Run 1: Invalidates and re-fetches ask-rides reactions (Friday + Sunday).
- Run 2: Invalidates and re-fetches driver reactions (Friday + Sunday).

**Skip condition:** Does nothing between 1 AM and 7 AM PT ("off-hours") to avoid unnecessary Discord API calls.

---

### `sync_rides_locations` — daily at 3 AM PT

Syncs location data from the external source (Google Sheets) into the `locations` database table.

---

## Pausing Jobs

Individual ride announcement jobs can be paused through the dashboard or via the API:

```bash
# Pause Friday job indefinitely
PUT /api/ask-rides/pauses/friday
{ "is_paused": true }

# Pause Friday, auto-resume after June 6 event
PUT /api/ask-rides/pauses/friday
{ "is_paused": true, "resume_after_date": "2025-06-06" }

# Resume immediately
PUT /api/ask-rides/pauses/friday
{ "is_paused": false }
```

Pause state is stored in the `message_schedule_pauses` table and survives restarts.

---

## Feature Flags for Jobs

Each job has a corresponding feature flag that must be enabled for the job to run. Flags are managed via `/feature-flag` in Discord or through the dashboard.

| Flag | Controls |
|------|----------|
| `ask_friday_rides_job` | Friday fellowship ride message |
| `ask_sunday_rides_job` | Sunday service ride message |
| `ask_sunday_class_rides_job` | Sunday class ride message |
| `ask_wednesday_rides_job` | Wednesday Bible study ride message |
| `ask_friday_drivers_job` | Friday driver availability message |
| `ask_sunday_drivers_job` | Sunday driver availability message |
| `rides_locations_sync_job` | Daily location sync from Google Sheets |

In `APP_ENV=local`, these flags are disabled at startup to prevent sending messages to Discord during development.

---

## Calendar Integration

Sunday jobs check the master calendar (Google Calendar, configured by `GOOGLE_CALENDAR_ID`) before sending. If the calendar has a "wildcard" event on that Sunday, the Sunday service message is skipped. If there is no "Sunday school" event, the Sunday class message is skipped.

When a Sunday message is suppressed due to a wildcard, the bot posts a notification to the driver bot spam channel explaining why.

---

## Adding a New Job

1. Create the job function in `bot/jobs/` (or a new file there).
2. Add a new `@log_job`-decorated async function.
3. Register it in `bot/cogs/job_scheduler.py` with an `AsyncIOScheduler.add_job()` call.
4. If it should be feature-flagged, add a new entry to `FeatureFlagNames` in `bot/core/enums.py` and decorate the function with `@feature_flag_enabled(FeatureFlagNames.YOUR_FLAG)`.

To disable a job without deleting it, move its file to `bot/jobs_disabled/`.
