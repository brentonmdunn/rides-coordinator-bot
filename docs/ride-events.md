# Database-backed ride events

Ride events own the ride date, requests, driver offers, and confirmed assignments.
Discord announcements are source projections. Dashboard, pickup, grouping, and
coverage reads use saved event state and do not require a live Discord bot.

## Data model

- `ride_events`: stable ID, guild, message type, and actual event date. The tuple
  `(guild_id, message_type, event_date)` identifies an event.
- `ride_announcements`: message/channel mapping, rider or driver kind, configured
  reaction choices, reconciliation time, clear/delete fences, and source errors.
- `ride_signups`: observed reaction choices keyed by message, Discord user ID, and
  emoji. Inactive choices retain removals for ordering and recovery.
- `ride_requests`: stable participants shared by Discord reactions, Something else
  submissions, manual riders, and the existing non-Discord pickup interface.
- `ride_driver_offers`: event-specific availability, offered legs, and explicitly
  confirmed passenger capacity. A reaction never invents a seat count.
- `ride_assignments`: confirmed request/driver pairs for pickup or return legs.

The existing pickup-info roster remains authoritative for registered names and
locations. Joins use immutable Discord IDs. Unregistered riders remain visible;
usernames are display/copy attributes, not identity keys. Legacy non-Discord rows
are retained for compatibility and written into canonical requests in the same
transaction. Current dated legacy entries are also imported during reconciliation.

Standard reaction choices yield pickup/return preferences. Unknown configured
emojis and conflicting preferences require coordinator review. Something else
text is saved before notification, so a failed coordinator notification does not
lose the request. A custom request can remain active after its reaction is removed.

Sunday class attendees are excluded from the service's outbound pickups by stable
identity and matching event date. They remain eligible for requested return legs.

## Synchronization and recovery

The sender saves an explicit event before posting, uses that date to render the
announcement, and binds the returned message ID before adding seed reactions.
Driver prompts are bound explicitly to dated events as well.

`RideEventSync` owns one serialized reconciliation loop. It runs on ready/resume
and every five minutes, retries failed discovery, and cancels on cog unload.
Sources are reconciled independently: an unavailable source cannot stop the other
snapshots. A complete snapshot is collected before replacing any saved choices.
Transport/permission failures preserve data and expose a sync error.

Raw gateway adds/removes are persisted before any message fetch, including when
member cache data is missing. Clear-all, removed-emoji, single-message deletion,
and bulk deletion are handled explicitly. Timestamp fences prevent older in-flight
snapshots or delayed gateway events from restoring cleared/deleted choices.
SQLite write serialization protects those checks against concurrent changes.

Deleting a source retires its reaction choices without deleting the event. Other
sources, manual requests, and durable custom requests remain independent. A driver
withdrawing availability retires affected confirmed assignments.

Startup discovery imports recognizable current-week announcements authored by
RideBot. Rider import requires an explicit displayed date and an unambiguous
current/default title; year boundaries are handled without using publication date
as the ride date. Legacy driver prompts are matched exactly and bound only when
there is one compatible, already-dated event. Ambiguous or older announcements
can be imported with explicit metadata using the single-message tool below.

## Coordinator interface

The dashboard links to `/ride-events`. Coordinators can:

1. Select a dated event and inspect requests, custom details, and sync freshness.
2. Add a manual rider without a Discord account.
3. Confirm a driver's passenger seats and offered legs.
4. Assign riders to pickup/return legs and save the whole plan atomically.
5. Refresh source reactions on demand when the bot is connected.

Plans reject cross-event IDs, inactive requests, unavailable drivers, unconfirmed
capacity, duplicate per-leg assignments, self-assignment, and capacity overflow.
Invalid updates preserve the previous plan. Seat/direction edits cannot invalidate
existing assignments. Coverage reflects confirmed assignments saved in this
interface; pasted grouping text and generated grouping suggestions are not a
confirmation. The LLM grouping engine itself remains a separate architecture item.

Reaction, pickup, grouping, coverage, and event views expose snapshot freshness.
The oldest active source snapshot controls freshness; an individual gateway event
cannot make incomplete history appear fully synced. Sources become stale after
15 minutes, on an incomplete initial snapshot, or on a source error. The UI also
ages freshness while a page stays open and polls current event data every minute.

## API

Event management endpoints require a ride coordinator or admin:

```text
GET  /api/ride-events?date_from=2026-10-19&date_to=2026-10-25
GET  /api/ride-events/{event_id}
GET  /api/ride-events/current/{friday|sunday|sunday_class|wednesday}
POST /api/ride-events/{event_id}/requests
PUT  /api/ride-events/{event_id}/driver-offers/{discord_user_id}
PUT  /api/ride-events/{event_id}/assignments
POST /api/ride-events/{event_id}/reconcile
```

List ranges are limited to 93 days and optionally accept `guild_id`. Details include
source state, reaction choices, canonical requests, offers, assignments, and
freshness. Reconciliation needs a live bot; reads and plan management do not.
The existing pickup/grouping endpoints also accept an explicit `event_id`.

Example replacement plan (IDs come from event detail):

```json
{"assignments": [{"request_id": 4, "driver_offer_id": 7, "direction": "pickup"}]}
```

## Rollout

The latest additive migration is `f2a3b4c5d607`, following `d1e2f3a4b506`.
The migration preserves earlier signup state before the first live snapshot.
From `backend/`, with the intended `DATABASE_URL` and `RIDEBOT_TOKEN` configured:

```sh
uv run python -m scripts.rollout_ride_events
uv run python -m scripts.rollout_ride_events --apply
```

The first command is a dry run. Apply creates a consistent online SQLite backup,
checks backup integrity, migrates the exact rollout revision, then imports and
reconciles existing announcements through REST. It starts no second gateway or
scheduler and sends no Discord messages. Failed source refreshes make the rollout
command fail; inspect event freshness and rerun after restoring access.

Use `--env-file PATH` to select a configuration. For an explicit migration without
Discord import, use `--apply --schema-only`. No production deployment is implied
by a local schema-only run. Backups retain the database suffix and stay ignored
by Git. Image rollback after a migration must use a schema-compatible image;
restore the backup only through an explicit operational recovery procedure.

For an ambiguous or historical announcement, use explicit metadata:

```sh
uv run python -m scripts.reconcile_ride_event \
  --channel-id 123 --message-id 456 \
  --message-type sunday_service --event-date 2026-10-25 \
  --emoji '🍔' --emoji '🏠' --emoji '✳️'
```

This is also a dry run by default; add `--apply` to write it. Repeated imports are
idempotent and conflicting bindings are rejected. If an announcement was sent but
its original binding failed, import its returned message ID rather than resending.
The app remains single-instance and uses SQLite; no worker service or queue was
introduced.
