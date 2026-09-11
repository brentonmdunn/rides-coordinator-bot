# Feature Flags

Feature flags control bot behavior and scheduled jobs at runtime without requiring a deployment. They are stored in the `feature_flags` database table and cached in memory.

---

## Managing flags

**Discord:** `/feature-flag <name> <true|false>` or `/list-feature-flags` to see all.

**Dashboard:** Admin-only **Feature Flags** panel.

**API:** `GET /api/feature-flags` and `PUT /api/feature-flags/{feature_name}`.

---

## Flag reference

### Core

| Flag | Default | Description |
|------|---------|-------------|
| `ridebot` | `true` | RideBot's per-bot kill switch. Applied to its cogs via the `@bot_enabled` decorator (`shared/utils/checks.py`), which resolves the flag for whichever bot is currently running instead of naming it directly. When disabled, all of RideBot's slash commands become no-ops. Each additional bot in the process gets its own kill-switch flag the same way. |
| `stonesbot` | copied from `ridebot` | StonesBot's per-bot kill switch, same mechanism as `ridebot` above. Its initial value is copied from `ridebot`'s value by the migration that introduced it, then managed independently. |

---

### Scheduled message jobs

These flags independently gate each automated ride/driver announcement. In `APP_ENV=local`, all of these are disabled on startup to prevent sending messages during development.

| Flag | Description |
|------|-------------|
| `ask_friday_rides_job` | Send the Friday fellowship ride request message on Wednesday at noon. |
| `ask_sunday_rides_job` | Send the Sunday service ride request message on Wednesday at noon. Also gated by the master calendar wildcard check. |
| `ask_sunday_class_rides_job` | Send the Sunday class ride request message. Only sent when the calendar has a "Sunday school" event. |
| `ask_wednesday_rides_job` | Send the Wednesday Bible study ride request message. |
| `ask_friday_drivers_job` | Send the Friday driver availability message to the driver chat channel. |
| `ask_sunday_drivers_job` | Send the Sunday driver availability message to the driver chat channel. |

---

### Behavior flags

| Flag | Description |
|------|-------------|
| `new_rides_msg` | Enable the newer ride message format (embed style). |
| `log_reactions` | Enable logging of reaction events (add/remove) on ride announcement messages to the `ride_reaction_events` table. Disable to stop collecting the reaction audit trail. |
| `event_threads` | Enable the auto-add-reactors-to-thread feature used by `/create-event-thread`. |
| `late_rides_react` | Enable handling for late ride reaction events. |
| `send_errors_to_discord` | Post unexpected error tracebacks to the bot logs Discord channel. Useful to disable in local/testing environments. |
| `use_cache` | Enable in-memory (or Redis) caching of Discord message lookups and reaction data. When disabled, every request hits the Discord API directly. |
| `agent` | Enable the conversational AI agent feature. |

---

## Caching

When `use_cache` is enabled, reaction data and message IDs are cached to reduce Discord API calls. The cache has namespace-scoped TTLs:

- During Wednesday active period (11 AM – 1 PM): 60-second TTL.
- During active hours (7 AM – 1 AM PT): 1-hour TTL.
- During off-hours: 7-hour TTL.

The `run_periodic_cache_warming` job warms the cache every 30 minutes during active hours.

Cache can be forcibly invalidated via `POST /api/cache/invalidate` (admin) or by restarting the backend.

---

## Adding a new flag

1. Add a new entry to `FeatureFlagNames` in `backend/shared/core/enums.py`.
2. Create an Alembic migration to insert the new row into `feature_flags`.
3. Use `@feature_flag_enabled(FeatureFlagNames.YOUR_FLAG)` decorator on the function to gate, or call `FeatureFlagsRepository.get_feature_flag_status(session, flag)` directly. A cog gating an entire bot's availability should use `@bot_enabled` instead — it resolves the current bot's own kill-switch flag automatically.
