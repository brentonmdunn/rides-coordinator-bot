# Hardcoded → Web-Configurable Candidates

Survey of bot functionality that is currently hardcoded in Python but could be made
human-editable via the web admin UI. Excludes the two changes already in open PRs:
ask-rides message text and ask-rides send time.

## Already web-configurable (for reference)

- Feature flags (jobs, message flags, cache, agent) — `/api/feature-flags`, `FeatureFlagsManager.tsx`, `feature_flags` table
- Job pause/resume with optional auto-resume date — `/api/ask-rides/pauses/{job_name}`, `message_schedule_pauses` table
- Fellowship season toggle (Friday ↔ Wednesday) — `/api/ask-rides/fellowship-season`, `global_settings` table
- Manual "send now" trigger for ask-rides messages
- User accounts, roles, invites — `/api/admin/users/`
- Discord driver / ride-coordinator role assignment — `/api/drivers/`, `/api/ride-coordinators/`
- Non-Discord rides (name, day, location, emoji tag) — `/api/non-discord-rides`
- Cache invalidation — `/api/cache/invalidate`

---

## High value — coordinators touch these per quarter/week

### 1. Wildcard / skip dates ⭐ recommended next PR
- `WILDCARD_DATES = ["6/20/25", "6/27/25", "6/29/25"]` — `backend/bot/jobs/ask_rides.py:59`
- `CLASS_DATES` (empty list, same file) — special Sunday class dates
- A hardcoded list of dates someone edits in code every school break.
- Fix: small `skip_dates` table + date picker on the dashboard + one check in
  `ask_rides.py`. The `resume_after_date` pattern in `message_schedule_pauses`
  already establishes the precedent. Small, self-contained, removes the most
  frequent remaining reason to edit code.

### 2. Leave/departure times
- Message text: "leave between 7 and 7:10pm" / "10 and 10:10am" / "8:30 and 8:40am"
  — `backend/bot/jobs/ask_rides.py:117-153`
- Duplicated as real logic in `backend/bot/services/group_rides_service.py:39-40`
  (Sunday 10:10 AM, Friday 7:10 PM departure times)
- If the message-editing PR makes text free-form, the message copies come along for
  free — but the `group_rides_service` values won't. Move those two values into the
  same settings store or they will drift from the message text.

### 3. Emoji reaction sets per ride type
- `BOT_REACTIONS` — `backend/bot/jobs/ask_rides.py:186-191`
  (🪨 Wed/Fri, 🍔 🏠 ✳️ Sunday service, 📖 Sunday class)
- Driver emoji sets — `backend/bot/services/driver_service.py:24-41`
- Emoji constants — `backend/bot/core/enums.py:215-240`
- Adding/removing a reaction option is a code change today.
- Caveat: reaction-counting logic and the non-Discord-rides UI both key off these
  emojis, so this is a medium-sized refactor (table + touch every consumer), not
  just a config table.

### 4. Remaining job schedule times
- Monday 11 AM Wednesday-fellowship reminder + Wednesday-noon main job —
  `backend/bot/cogs/job_scheduler.py:34-80`, `backend/bot/utils/constants.py:117-118`
  (`RIDE_CYCLE_START_HOUR`, `WED_FELLOWSHIP_SEND_HOUR`)
- Should ride on the same `AskRidesSchedule` mechanism the send-time PR introduces,
  if it doesn't already cover them.
- Cache-warming interval (every 30 min) and 3 AM locations sync are fine hardcoded.

---

## Medium value — changes occasionally, per school year

### 5. Pickup locations + GPS + mappings
- `PickupLocations` / `CampusLivingLocations` enums — `backend/bot/core/enums.py:117-152`
- GPS coordinates / Maps links — `backend/bot/utils/constants.py:21-34`
- Location group lists (scholars / warren+pepper canyon / rita) — `backend/bot/utils/constants.py:54-72`
- Campus → pickup mapping — `backend/bot/services/group_rides_service.py:43-55`
- Housing group categories — `backend/bot/services/housing_group_service.py:42-67`
- Travel-time matrix between pickups — `backend/bot/utils/locations.py:11-60`
- Locations do change (new dorms, moved pickup spots) and today require touching 4+
  files. High-leverage but a bigger project: move to an admin-editable `locations`
  table (a locations repo/CSV sync already exists). The travel-time matrix is the
  awkward part — it would need admin editing too.

### 6. Channel and role targets
- Channel IDs (rides announcements, driver chat, logs, driver spam, new-rides
  category) — `backend/bot/core/enums.py:6-21, 114`
- Role IDs (driver, rides, ride coordinator) — `backend/bot/core/enums.py:51-53`
- Command channel whitelists — `backend/bot/utils/channel_whitelist.py:11-20`
- Ride-coverage scanned channels — `backend/bot/services/ride_coverage_service.py:136-139`
- Agent allowed channels — `backend/bot/cogs/agent.py:24-30`
- Welcome-message channel — `backend/bot/services/ride_request_service.py:83`
- Web-editable channel/role pickers would make the bot portable to another server,
  but these ~never change in practice, so lower urgency.

### 7. Other message text
- New-rider welcome message — `backend/bot/services/ride_request_service.py:82-87`
- Ask-rides header text ("for this week!" / "for Sunday Service!") — `backend/bot/jobs/ask_rides.py:424-426`
- Embed titles + colors per ride type (`RIDE_TYPES_CONFIG`) — `backend/bot/jobs/ask_rides.py:161-178`
- Natural extension of the message-editing PR's settings store.

---

## Low value — leave hardcoded

- **Cache TTLs / thresholds** — `backend/bot/utils/constants.py:88-111` (session TTL,
  reaction cache windows, message history limit) and agent knobs in
  `backend/bot/cogs/agent.py:20-23`. Operator tuning, not coordinator-facing;
  env vars at most.
- **Guild ID, category IDs** — `backend/bot/utils/constants.py:5`. Deployment config;
  belongs in env, not a UI.
- **Message-detection keywords** — "drive:" (`ride_coverage_service.py:143`),
  "sunday service" / "friday night fellowship" (`ask_rides.py:453-454, 565-570`,
  `group_rides_service.py:99-102`, `reaction_logging_service.py:170-173`).
  Coupling parsing keywords to a UI invites breakage; keep in code.
- **Active-hours / ride-cycle time windows** — `backend/bot/utils/constants.py:115-117`,
  `backend/bot/utils/time_helpers.py:52-135`. Deeply woven into caching and coverage
  logic; only revisit if event days themselves become configurable.

---

## Recommendation

1. **Next PR: skip/wildcard dates** — one table, one route, one dashboard widget,
   one check in `ask_rides.py`; follows existing patterns.
2. **Then:** fold `group_rides_service.py` departure times into the same settings
   store as the message templates so message text and grouping logic can't drift.
3. **Bigger backlog items:** emoji reaction sets, then locations.
