# Design: Configurable Ask-Rides Send Schedule

Ride coordinators can edit *when* the ask-rides jobs fire — day of week and
time of day — from the admin site. Changes take effect immediately (live
APScheduler reschedule, no bot restart), fall back to today's hardcoded times
when no saved config exists, and propagate to every open admin session via the
existing SSE stream.

---

## Requirements

| Requirement | Decision |
|---|---|
| What's configurable | Day-of-week **and** time-of-day per schedule slot |
| Granularity | **Two** independently configurable slots, not four — see "Current state" below |
| Apply timing | Live reschedule via `scheduler.reschedule_job(...)` — no restart |
| Wednesday's day/time relationship | Absolute day+time (no more "2 days before the event" offset math) |
| Validation | Per-slot allowed days + a daytime time window (see below) |
| Ride-cycle boundary | Redefined as the **calendar week: Monday 00:00 → Sunday 23:59**, with a schedule-aware "sent yet?" check — every saveable schedule is then structurally consistent, no warning machinery needed (see "Ride-cycle boundary" section) |
| Permissions | `require_ride_coordinator` (same tier as the message-templates feature) |
| Propagation | Reuse the existing `messages_broadcaster` SSE stream with a new event type |

---

## Current state (for reference)

All scheduling lives in `bot/cogs/job_scheduler.py`, registered once at cog
load with hardcoded `CronTrigger`s and explicit job IDs:

```python
self.scheduler.add_job(
    run_ask_rides_all,
    CronTrigger(day_of_week="wed", hour=12, minute=0),
    id="run_ask_rides_all",
    args=[bot, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS],
)
self.scheduler.add_job(
    run_ask_rides_wed,
    CronTrigger(day_of_week="mon", hour=11, minute=0),
    id="run_ask_rides_wed",
    args=[bot],
)
```

**Key finding: there are only two independent triggers today, not four.**
`run_ask_rides_all` fires once (Wed noon) and internally sends the shared
`@Rides` header ping, then Friday fellowship, Sunday class, and Sunday
service back-to-back (`bot/jobs/ask_rides.py` — `run_ask_rides_header` →
`run_ask_rides_fri` / `run_ask_rides_sun_class` / `run_ask_rides_sun`).
`run_ask_rides_wed` (the Wednesday-fellowship reminder) is the only other
trigger, firing Monday 11am — two days ahead of the Wednesday event via
convention, not code.

This matches what was asked for: **one schedule slot for "Wednesday
fellowship reminder"** and **one shared schedule slot for the "Friday/Sunday
group"**. No job-splitting is required — the combined header ping and batched
send stay exactly as they are; only the trigger's day/time becomes
DB-backed and editable instead of a hardcoded `CronTrigger(...)` literal.

**Three sources of truth exist today and all need to move to the new config:**
- The actual trigger, in `job_scheduler.py`.
- Display-only helpers in `bot/utils/time_helpers.py` —
  `get_next_monday_11am()` and `get_next_wednesday_noon()` — hardcode
  "11am"/"noon" text independently (via the `WED_FELLOWSHIP_SEND_HOUR`
  constant, `bot/utils/constants.py:134`), consumed by `get_ask_rides_status`
  / `get_next_run_time` in `bot/jobs/ask_rides.py` for the dashboard's "next
  run" display. These currently only stay correct by convention matching the
  cron literals.
- **Pause auto-resume logic**: `MessageScheduleRepository.is_job_paused`
  (`bot/repositories/message_schedule_repository.py:141-155`) and the
  pause-status display in `bot/jobs/ask_rides.py:592` both call
  `get_send_wednesday(resume_after_date)` — i.e. they hardcode the assumption
  that sends happen on Wednesday. If the Fri/Sun group send moves to another
  day, pauses would auto-resume against the wrong send day and a paused job
  could fire a week early. Both call sites must switch to a schedule-aware
  helper (see §7).

A related hardcoded convention, `RIDE_CYCLE_START_DAY`/`_HOUR` (Wed noon —
`time_helpers.py:191`, `constants.py:133`), backs the dashboard's
"sent this week" logic and only works because it happens to equal the batch
send time. It gets **redefined to the calendar week** rather than moved into
the config — see the "Ride-cycle boundary" section below.

**Latent timezone bug worth fixing alongside this:** `AsyncIOScheduler()` is
constructed with no `timezone=` argument (`job_scheduler.py:24`), so cron
fires in the *container's* OS timezone, not `LA_TZ`. `Dockerfile.preprod`
sets `ENV TZ="America/Los_Angeles"` but the main `Dockerfile` sets no `TZ` at
all. Since we're about to let coordinators pick a day/time and need it to
mean what it says regardless of container config, this design pins
`AsyncIOScheduler(timezone=LA_TZ)` explicitly.

---

## Backend plan

### 1. Enum (`bot/core/enums.py`)

```python
class AskRidesScheduleSlot(StrEnum):
    """The two independently-schedulable ask-rides send slots."""

    WEDNESDAY_REMINDER = "wednesday_reminder"   # run_ask_rides_wed
    FRI_SUN_GROUP = "fri_sun_group"              # run_ask_rides_all
```

### 2. Model + migration

```python
class AskRidesSchedule(Base):
    """Model representing a customized send day/time for an ask-rides schedule slot."""

    __tablename__ = "ask_rides_schedules"

    slot: Mapped[str] = mapped_column(primary_key=True)  # AskRidesScheduleSlot value
    # plain str, not SQLEnum — matches AskRidesMessageTemplate.message_type
    day_of_week: Mapped[int]   # 0=Monday .. 6=Sunday, matches DaysOfWeekNumber
    hour: Mapped[int]
    minute: Mapped[int]
    updated_by: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

Rows created lazily on first save, same pattern as `AskRidesMessageTemplate` —
absence ⇒ default. Alembic migration via
`uv run alembic revision --autogenerate -m "add ask_rides_schedules"`.

### 3. Defaults (`bot/utils/ask_rides_schedule_defaults.py`)

```python
@dataclass(frozen=True)
class ScheduleDefault:
    day_of_week: int
    hour: int
    minute: int

DEFAULT_SCHEDULE: dict[AskRidesScheduleSlot, ScheduleDefault] = {
    AskRidesScheduleSlot.WEDNESDAY_REMINDER: ScheduleDefault(day_of_week=0, hour=11, minute=0),  # Mon 11am
    AskRidesScheduleSlot.FRI_SUN_GROUP: ScheduleDefault(day_of_week=2, hour=12, minute=0),        # Wed noon
}
```

### 4. Repository (`bot/repositories/ask_rides_schedule_repository.py`)

Standard conventions: `@staticmethod`, `session` first param.
- `get_all(session) -> list[AskRidesSchedule]`
- `get(session, slot) -> AskRidesSchedule | None`
- `upsert(session, slot, day_of_week, hour, minute, updated_by)`
- `delete(session, slot)` — reset to default

### 5. Service (`bot/services/ask_rides_schedule_service.py`)

- `get_effective_schedule(slot) -> EffectiveSchedule` (`day_of_week`, `hour`,
  `minute`, `is_customized`) — merges DB row over `DEFAULT_SCHEDULE`; wraps
  the query in try/except, falls back to the default on any DB error
  (`logger.exception`, never raises — same rule as the message-templates
  service, since a DB hiccup must never leave a job unscheduled).
- `get_effective_schedules() -> dict[slot, EffectiveSchedule]` — all slots at once (for the GET route).
- `update_schedule(slot, day_of_week, hour, minute, updated_by) -> EffectiveSchedule`:
  1. Validate (raises `ValueError` → caller maps to 422):
     - `hour`/`minute` in range, and the time falls inside the daytime window
       **6:00 ≤ time ≤ 22:00** inclusive (so 22:00 is allowed, 22:30 is not —
       rejects e.g. a 3am send from a typo).
     - **Per-slot allowed days** — the send day must precede the first event
       the slot announces, because message bodies compute "next <day>" at
       send time and `get_next_date_str` skips to *next week* when the target
       day is today (`time_helpers.py:275-277`). Sending the Friday message
       on Friday would advertise next week's date:
       - `WEDNESDAY_REMINDER`: day ∈ {Mon, Tue} — Sunday is deliberately
         excluded: a Sunday send falls in the *previous* Monday-start week
         (see "Ride-cycle boundary"), which would break "sent this week"
         detection. Cutting it makes every legal schedule week-consistent.
       - `FRI_SUN_GROUP`: day ∈ {Mon, Tue, Wed, Thu}
  2. Upsert via the repository.
  3. **Apply live**: call a new `reschedule_job(slot, day_of_week, hour, minute)`
     helper (below) so the running APScheduler job picks up the new trigger
     immediately.
  4. `await invalidate_namespace(CacheNamespace.ASK_RIDES_STATUS)` — the
     dashboard's "next run" comes from the cached status endpoint; without
     this, the SSE-triggered refetch in step 5 would re-serve the stale
     pre-change value until the TTL expires (the pause and fellowship-season
     routes already do this — `api/routes/ask_rides.py:141,163,284`).
  5. Publish `{"type": "schedule_updated", "slot": slot.value}` on the
     existing `messages_broadcaster` (reusing that channel rather than
     standing up a second SSE stream — the payload is already a
     type-discriminated dict and clients don't trust the payload for data
     regardless).
  6. Return the effective schedule.
- `reset_schedule(slot)` — delete the row, reschedule back to the default trigger, publish the same event type.

### 6. Live rescheduling

New helper, e.g. `bot/core/scheduler_control.py`:

```python
def reschedule_job(job_id: str, *, day_of_week: int, hour: int, minute: int) -> bool:
    """Reschedule a running APScheduler job. Returns False if the bot/scheduler isn't up yet."""
    bot = get_bot()
    if bot is None:
        logger.warning("Cannot reschedule %s — bot not ready", job_id)
        return False
    cog = bot.get_cog("JobScheduler")
    if cog is None:
        logger.warning("Cannot reschedule %s — JobScheduler cog not loaded", job_id)
        return False
    cog.scheduler.reschedule_job(
        job_id,
        trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=LA_TZ),
    )
    return True
```

`AskRidesScheduleSlot` maps to APScheduler job IDs:
`{WEDNESDAY_REMINDER: "run_ask_rides_wed", FRI_SUN_GROUP: "run_ask_rides_all"}`.

**Startup wiring** (`job_scheduler.py`): instead of hardcoded `CronTrigger`
literals, `JobScheduler.__init__` calls
`AskRidesScheduleService.get_effective_schedule(slot)` for each of the two
slots before `add_job(...)`, and constructs `AsyncIOScheduler(timezone=LA_TZ)`.
If the service call fails for any reason (fresh DB, migration not yet run)
the defaults are used automatically — same fallback guarantee as the
templates feature, so a broken schedule config can never leave the bot
unable to start.

**If the bot process isn't up when a save happens** (API-only deploy, bot
mid-restart): `update_schedule`/`reset_schedule` still persist to the DB
(so the *next* startup picks up the right trigger) but `reschedule_job(...)`
returns `False`. The route surfaces this as a `warning` field ("saved, but
will not take effect until the bot reconnects") rather than failing the
request — mirrors the coordinator-setting feature's "best-effort verification,
never a hard dependency" pattern.

### 7. Job wiring cleanup

- `get_next_monday_11am()` / `get_next_wednesday_noon()` in
  `bot/utils/time_helpers.py` are replaced by a single
  `get_next_schedule_occurrence(slot)` that reads the effective schedule and
  computes the next matching day/time — the dashboard's "next run" display and
  the actual trigger now share one source of truth. `get_next_run_time()` /
  `get_ask_rides_status()` in `bot/jobs/ask_rides.py` call this instead.
- **Delete `WED_FELLOWSHIP_SEND_HOUR`** (`bot/utils/constants.py:134`) once
  `get_next_monday_11am()` is gone — no stale copy of the send time may
  survive outside the config. Grep-verify at implementation time.
- **Fix pause auto-resume**: replace both `get_send_wednesday(...)` call
  sites (`message_schedule_repository.py:141-155` for resume logic,
  `ask_rides.py:592` for pause-status display) with a schedule-aware
  `get_send_day_before(event_date, slot)` that computes "the configured send
  day immediately before this event date" from the effective schedule. Note
  this puts a service/config read inside repository logic — pass the
  effective schedule *into* `is_job_paused` from the service layer rather
  than having the repository fetch it, keeping repo conventions intact.

### 8. Ride-cycle boundary — redefined as the calendar week (Mon 00:00 → Sun 23:59)

The Wed-noon "ride cycle" has exactly two consumers, both in the dashboard's
status path (`get_ask_rides_status`):

- `get_current_cycle_start()` (`time_helpers.py:349-364`) — the channel-history
  cutoff for "was the Friday/Sunday message sent this week"
  (`ask_rides.py:609`).
- `is_ride_cycle_active()` (`time_helpers.py:333-347`) — the "this week's
  messages should exist by now" window, Wed 12:00 → Sun 23:59
  (`ask_rides.py:570`).

Both encode the send moment by convention, so *any* configurable schedule
drifts from them. Rather than keeping the fixed boundary and warning on
drift, this design redefines the week and makes the send check
schedule-aware — after which **no legal schedule can drift, and no warning
machinery is needed**:

- **`get_current_cycle_start()` → most recent Monday 00:00.** This is exactly
  the window the Wednesday job already uses (`ask_rides.py:611-614` computes
  `monday_week_start` with the comment that Wednesday uses "the Mon-Sun
  window, not the Wed-Sun ride cycle") — the codebase converges on one week
  definition instead of two. `RIDE_CYCLE_START_DAY`/`_HOUR` and the special
  Monday/Tuesday step-back logic are updated/deleted accordingly, and the
  separate `monday_week_start` computation collapses into it.
- **`is_ride_cycle_active()` → replaced by a per-slot, schedule-aware check**:
  `has_send_time_passed(slot)` = "is `now` at/after this week's configured
  send datetime for this slot?" (computed from the effective schedule via the
  same `get_next_schedule_occurrence` machinery in §7). That is the question
  the dashboard was actually asking; a fixed window only ever approximated it.
- Combined with the per-slot allowed days in §5 (`WEDNESDAY_REMINDER` ∈
  {Mon, Tue}, `FRI_SUN_GROUP` ∈ {Mon–Thu}), every saveable schedule sends
  within the same Monday-start week as the events it announces —
  consistency is structural, not advisory.

**One visible behavior change** (accepted): on Monday/Tuesday the dashboard
previously showed *last* week's Friday/Sunday messages as the current
cycle's "last message" (cutoff = previous Wed noon). With the Monday-start
week it shows "not sent yet this week" instead — the more truthful display.
Note this in the PR description.

### 9. API routes (`api/routes/ask_rides.py`, same router)

| Route | Auth | Behavior |
|---|---|---|
| `GET /api/ask-rides/schedule` | `require_ride_coordinator` | Both slots' effective day/time + `is_customized` + per-slot allowed days + time window |
| `PUT /api/ask-rides/schedule/{slot}` | `require_ride_coordinator` | Body `{day_of_week, hour, minute}`. 422 on a day outside the slot's allowed set or a time outside the daytime window. Invalidates `ASK_RIDES_STATUS` cache. Returns updated effective schedule + optional `warning` if live reschedule couldn't be applied |
| `DELETE /api/ask-rides/schedule/{slot}` | `require_ride_coordinator` | Reset to default, same cache-invalidation/live-reschedule/warning behavior |

No new SSE route — the existing `/api/ask-rides/messages/stream` now also
emits `schedule_updated` events; the frontend hook already treats events as
opaque invalidation triggers.

---

## Frontend plan

Small addition to the existing `MessageTemplatesEditor.tsx` section (or a
sibling component in the same `AskRidesDashboard` collapsible area) — two
rows, one per slot:

- Day-of-week `<select>` (options limited to the slot's allowed days from
  the GET response) + time input (`<input type="time">`), pre-filled from
  the effective schedule.
- "Customized" badge + amber "Reset to default" button, same convention as
  the message templates.
- Inline preview: "Next send: <computed next occurrence>" using the same
  upcoming-dates-style formatting already used elsewhere in the dashboard.
- Save → PUT mutation → invalidate the same `['askRidesMessages']`-adjacent
  query key (or a new `['askRidesSchedule']` key) on success; SSE
  `schedule_updated` events invalidate the same way.
- If a save returns a `warning` (bot not connected), show it inline instead
  of a hard error — the value was still persisted.

---

## Testing

- **Unit — service**: default fallback when row/table missing; validation
  rejects days outside the slot's allowed set (e.g. Friday for
  `FRI_SUN_GROUP`), out-of-range hour/minute, and times outside 6:00–22:00
  inclusive (22:00 accepted, 22:30 rejected); Sunday rejected for
  `WEDNESDAY_REMINDER`; `ASK_RIDES_STATUS` cache invalidated on update and
  reset; `reschedule_job` failure (bot not ready) doesn't raise and is
  surfaced as a return value, not an exception.
- **Unit — week boundary**: `get_current_cycle_start()` returns the most
  recent Monday 00:00 (including on Monday itself); `has_send_time_passed`
  is False before and True after this week's configured send datetime,
  for both default and customized schedules.
- **Unit — pause interaction**: with a customized send day, pause
  auto-resume expires against the *configured* send day, not Wednesday —
  regression test for the `get_send_wednesday` replacement.
- **Unit — scheduler wiring**: `JobScheduler.__init__` uses the DB-configured
  time when present, defaults otherwise; `AsyncIOScheduler` is constructed
  with `timezone=LA_TZ`.
- **Unit — routes**: 403 for viewer role; PUT validation errors; PUT→GET
  round trip; DELETE resets `is_customized`; warning field present when
  reschedule can't be applied live.
- **Frontend**: component test mirroring `MessageTemplatesEditor.test.tsx` —
  load → change day/time → save → PUT called with right body; reset flow.

## Rollout / order of work

1. Enum + model + migration + defaults.
2. Repository + service (with fallback + validation) + `scheduler_control.py` + unit tests.
3. Wire `job_scheduler.py` to read from the service at startup; pin scheduler timezone; replace the two hardcoded display helpers in `time_helpers.py`; fix the two `get_send_wednesday` pause call sites; delete `WED_FELLOWSHIP_SEND_HOUR`; redefine the cycle to the Monday-start week and replace `is_ride_cycle_active()` with the schedule-aware `has_send_time_passed(slot)`.
4. API routes (reusing the existing router/SSE stream) + tests.
5. Frontend rows in `MessageTemplatesEditor.tsx` + test.
6. `uv run invoke format && uv run invoke lint && uv run ty check`, `npm run lint`, `npx tsc --noEmit`, `uv run pytest`.

## Open edge cases handled

- **Table doesn't exist / DB unreachable**: falls back to hardcoded defaults at both startup and API-read time — the bot can always come up and the dashboard can always render.
- **Bot down when a save happens**: DB write still succeeds (next restart honors it); live reschedule is best-effort and surfaces a non-blocking warning.
- **Container TZ drift**: fixed at the source by pinning `AsyncIOScheduler(timezone=LA_TZ)`, so a save always means what it says regardless of the container's OS timezone.
- **Two sources of truth for "next run" text**: eliminated — `get_next_schedule_occurrence(slot)` is the only place that computes it, backing both the real trigger and the dashboard display.
- **Pause auto-resume vs. custom send day**: fixed — resume expiry is computed against the configured send day, not a hardcoded Wednesday.
- **Stale dashboard after a save**: fixed — the PUT invalidates the `ASK_RIDES_STATUS` cache before publishing the SSE event, so the triggered refetch returns fresh data.
- **Message advertises the wrong week**: prevented — per-slot allowed days guarantee the send precedes the announced event, so `get_next_date_str` can't skip to next week.
- **Ride-cycle drift**: designed out — the week is the calendar week (Mon 00:00 → Sun 23:59), the "sent yet?" check derives from the configured schedule, and per-slot allowed days keep every send inside its events' week. No warning machinery needed (see §8).
- **Mid-week reschedule double-send/skip**: accepted, not guarded — moving a schedule after this week's send has fired can make it fire again this week (or moving it earlier can skip a week). The "Next send:" preview makes the consequence visible before saving; a last-sent guard is deliberately out of scope.
