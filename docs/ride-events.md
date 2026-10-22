# Database-backed ride events: first increment

This is the first stage of [recommendation 1](greenfield-architecture-review.md).
Existing dashboard, pickup, and grouping flows continue to use their current
sources during this migration. The new API is available for validation and future
consumer migration; this increment does not claim to finish that migration.

## Data ownership

- `ride_events` stores a stable event ID, Discord guild ID, message type, and the
  actual ride date. `(guild_id, message_type, event_date)` identifies an event.
- `ride_announcements` maps Discord message IDs to events, channels, and the
  configured signup emojis. Multiple announcements may reference one event.
- `ride_signups` stores current reaction choices by message ID, immutable Discord
  user ID, and emoji. Removals are retained as inactive choices. Multiple active
  choices/messages are grouped into one rider in the API.
- The existing pickup-info roster remains the source for registered people's
  names and locations. Reads join it by Discord user ID, without matching names
  or usernames. Unregistered riders remain visible with null roster fields.

Reaction choices are deliberately preserved rather than interpreted as validated
pickup/return commitments: templates allow customized emojis. Driver offers,
assignments, custom requests, and non-Discord requests are later stages.

## New announcement and reaction flow

The normal ask-rides sender persists an event before sending its announcement,
using the same explicit date to render the embed. After sending, it binds the
message before adding seed reactions. If sending fails, the event remains with
no announcement. If binding fails, an error includes the event/channel/message
IDs for recovery; the sender does not silently resend and create duplicates.

Raw reaction handlers persist configured choices on mapped messages before
fetching the message or running other Discord actions. Repeated deliveries update
the same choice. Observation timestamps prevent older snapshots or events from
overwriting newer recorded changes. The legacy reaction audit log uses explicit
event metadata for registered messages, while retaining its previous fallback for
unregistered historical announcements.

## Read API

Both endpoints require the ride coordinator role and work without a live bot:

```text
GET /api/ride-events?date_from=2026-10-19&date_to=2026-10-25
GET /api/ride-events/{event_id}
```

The list optionally accepts `guild_id` and requires a date range of at most 93
days. Detail responses include source announcements, their configured emojis,
`last_reconciled_at`, and each rider's active choices, observed timestamps, and
available roster identity/location. Timestamps carry a UTC offset.

Stored state can be stale. `last_reconciled_at: null` means no complete snapshot
has been applied; receiving individual gateway updates does not establish that
all earlier reactions were observed.

## Migration and importing current announcements

The additive Alembic revision is `d1e2f3a4b506`, following `c8d2e4f6a901`.
Apply migrations through the normal deployment process before enabling this code.
No production or local application database is migrated by the test suite.

Historical reaction logs do not reliably contain the actual event date. They are
not automatically backfilled into events. Import existing announcements with
explicit dates and reaction configuration instead. From `backend/`, with
`DATABASE_URL` and `RIDEBOT_TOKEN` configured:

```sh
uv run python -m scripts.reconcile_ride_event \
  --channel-id 123 --message-id 456 \
  --message-type sunday_service --event-date 2026-10-25 \
  --emoji '🍔' --emoji '🏠' --emoji '✳️'
```

The default is a dry run: read the complete Discord reaction snapshot and report
the intended metadata/count without writing data. Add `--apply` to register the
announcement and replace its current choices. Reuse the same arguments to repair
missed adds/removals. Registration is idempotent, and conflicting message bindings
are rejected. A failed snapshot fetch does not clear saved signups. The tool logs
in through REST only; it starts no gateway connection or scheduled jobs.

Reconciliation must run against the same database as the app. Run the tool again
after importing a busy announcement if reactions changed while it was first
being bound. Snapshot application preserves gateway observations recorded after
the snapshot began and rolls back all state changes if a database write fails.

## Remaining work before switching existing consumers

1. Reconcile automatically on startup/reconnect and periodically as needed.
2. Handle bulk reaction removal and deleted source messages explicitly. For now,
   clear-all/remove-emoji changes require reconciliation; deleted announcements
   retain their last recorded choices rather than implying cancellation.
3. Complete ingestion for members absent from the guild cache.
4. Move pickup/dashboard reads to these event IDs and surface freshness in the UI.
5. Unify non-Discord/custom requests and define explicit pickup/return semantics,
   then add driver offers and assignments.

The current application remains single-instance. This implementation uses SQLite
upserts and does not introduce a queue or another service.
