# API Reference

All routes are served by the FastAPI backend. In production, the backend and frontend share an origin, so paths are relative (`/api/...`). In local dev, prefix with `http://localhost:8000`.

Authentication details are in [auth.md](auth.md). Most routes require at least `ride_coordinator` role. Routes marked **admin** require `admin` role. Routes marked **open** have no auth requirement (other than a valid session).

---

## Infrastructure

### `GET /health` — open

Returns overall health of the bot and database. No auth required.

**Response**
```json
{
  "status": "ok",
  "bot": "connected",
  "database": "connected"
}
```

`status` is `"ok"` only when both `bot` and `database` are `"connected"`. Otherwise `"degraded"`.

---

### `GET /api/environment` — open

Returns the current `APP_ENV` value (`local`, `preprod`, or `prod`).

---

### `GET /api/me` — authenticated

Returns the current user's email and role.

**Response**
```json
{
  "email": "user@example.com",
  "role": "ride_coordinator",
  "is_local": false
}
```

Roles: `viewer`, `ride_coordinator`, `admin`.

---

### `PUT /api/me/role` — local only

Switch the dev user's role. Only works when `APP_ENV=local`.

**Request body**
```json
{ "role": "admin" }
```

---

### `GET /api/me/preferences`

Returns the authenticated user's preferences. Creates a default row on first call.

**Response**
```json
{ "show_map_labels": true }
```

---

### `PATCH /api/me/preferences`

Update one or more preferences. Only supply fields you want to change.

**Request body** (all optional)
```json
{ "show_map_labels": false }
```

---

## Auth (self-hosted OAuth)

See [auth.md](auth.md) for the full OAuth flow. These routes are only active when `AUTH_PROVIDER=self`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/auth/discord/login` | Redirect to Discord OAuth |
| `GET` | `/api/auth/discord/callback` | OAuth callback, sets session cookie |
| `POST` | `/api/auth/logout` | Deletes session, clears cookie |

---

## Admin — User Management

All routes below require the `admin` role.

### `GET /api/admin/users`

List all user accounts.

**Response**
```json
{
  "users": [
    {
      "id": 1,
      "email": "user@example.com",
      "discord_username": "someuser",
      "discord_user_id": "123456789",
      "role": "ride_coordinator",
      "role_edited_by": null,
      "invited_by": "admin@example.com",
      "created_at": "2025-01-01T00:00:00"
    }
  ],
  "current_user_email": "admin@example.com",
  "admin_emails": ["admin@example.com"]
}
```

---

### `POST /api/admin/users/invite`

Invite a new user by Discord username. Creates a `user_accounts` row with no email; email is linked on first login.

**Request body**
```json
{
  "discord_username": "someuser",
  "role": "viewer"
}
```

**Response** — the created account object.

Returns `409` if an account for that username already exists.

---

### `DELETE /api/admin/users/{account_id}`

Revoke a user account or pending invite. Cannot revoke root admins (seeded from `ADMIN_EMAILS`).

---

### `PUT /api/admin/users/{email}/role`

Update a user's role. Cannot change your own role or root admin roles.

**Request body**
```json
{ "role": "ride_coordinator" }
```

---

## Feature Flags

### `GET /api/feature-flags` — admin

List all feature flags and their enabled state.

**Response**
```json
{
  "flags": [
    { "id": 1, "feature": "bot", "enabled": true }
  ]
}
```

See [feature-flags.md](feature-flags.md) for the full flag reference.

---

### `PUT /api/feature-flags/{feature_name}` — admin

Enable or disable a flag.

**Request body**
```json
{ "enabled": true }
```

---

## Ask Rides

These endpoints control the automated ride announcement messages sent to the rides channel.

### `GET /api/ask-rides/status`

Get the current status of all three ask-rides jobs (`friday`, `sunday`, `sunday_class`).

**Response** — one key per job:
```json
{
  "friday": {
    "enabled": true,
    "will_send": true,
    "sent_this_week": false,
    "reason": null,
    "next_run": "2025-05-07T12:00:00-07:00",
    "last_message": { "message_id": "123", "reactions": { "🪨": 5 } },
    "pause": { "is_paused": false, "resume_after_date": null, "resume_send_date": null }
  }
}
```

`reason` is `null` when the job will run, `"feature_flag_disabled"` when the flag is off, `"wildcard_detected"` when the calendar indicates a skip, or `"no_class_scheduled"` for `sunday_class`.

---

### `POST /api/ask-rides/send-now` — ride_coordinator

Manually trigger all ask-rides messages immediately. Runs the same logic as the Wednesday scheduler.

**Response**
```json
{ "success": true, "message": "Ask rides messages sent successfully" }
```

---

### `GET /api/ask-rides/pauses`

Get pause state for all three jobs.

**Response**
```json
{
  "friday": {
    "is_paused": false,
    "resume_after_date": null,
    "resume_send_date": null
  }
}
```

---

### `PUT /api/ask-rides/pauses/{job_name}` — ride_coordinator

Pause or resume a specific job. `job_name` must be one of `friday`, `sunday`, `sunday_class`.

**Request body**
```json
{
  "is_paused": true,
  "resume_after_date": "2025-06-01"
}
```

`resume_after_date` is optional. When set, the job automatically resumes after that event date. To resume immediately, send `{ "is_paused": false }`.

---

### `GET /api/ask-rides/upcoming-dates/{job_name}`

Get projected upcoming event dates for a job.

**Query params**

| Param | Default | Description |
|-------|---------|-------------|
| `count` | `6` | Number of dates to return |
| `offset` | `0` | Dates to skip (for pagination) |

**Response**
```json
{
  "dates": [
    {
      "event_date": "2025-05-09",
      "send_date": "2025-05-07",
      "label": "Fri May 9"
    }
  ],
  "has_more": true
}
```

`send_date` is the Wednesday before the event when the message will actually be sent.

---

### `GET /api/ask-rides/reactions/{message_type}`

Get the full reaction breakdown for the current week's ask-rides message.

`message_type` must be one of `friday`, `sunday`, `sunday_class`.

**Response**
```json
{
  "message_type": "friday",
  "reactions": { "🪨": ["username1", "username2"] },
  "username_to_name": { "username1": "First Last" },
  "non_discord": [{ "name": "First Last", "location": "Seventh mail room" }],
  "message_found": true
}
```

---

## Pickup Locations & Route Builder

### `GET /api/pickup-locations`

Get all pickup locations with coordinates and Google Maps links.

**Response**
```json
{
  "locations": [
    { "key": "SEVENTH", "value": "Seventh mail room" }
  ],
  "map_links": { "Seventh mail room": "https://maps.google.com/..." },
  "coordinates": { "Seventh mail room": { "lat": 32.88, "lng": -117.23 } }
}
```

---

### `POST /api/make-route`

Generate a formatted driving route string from locations and departure time.

**Request body**
```json
{
  "locations": ["SEVENTH", "ERC", "MARSHALL"],
  "leave_time": "7:10 PM"
}
```

**Response**
```json
{
  "success": true,
  "route": "Drive: @user1 @user2 ...",
  "error": null
}
```

---

## List Pickups

### `POST /api/list-pickups`

Get pickup locations from reactions on a ride announcement message, grouped by housing area.

**Request body**
```json
{
  "ride_type": "friday",
  "message_id": null,
  "channel_id": "939950319721406464"
}
```

`ride_type` must be `friday`, `sunday`, or `message_id`. When using `message_id`, you must supply `message_id`.

**Response**
```json
{
  "success": true,
  "data": {
    "housing_groups": {
      "Scholars": {
        "emoji": "🏫",
        "count": 3,
        "locations": {
          "Seventh mail room": [
            { "name": "First Last", "discord_username": "someuser", "drive_back": false }
          ]
        }
      }
    },
    "unknown_users": ["unknownuser"]
  }
}
```

---

## Check Pickups / Ride Coverage

### `GET /api/check-pickups/{ride_type}`

Check which users who requested a ride have been assigned to one. `ride_type` must be `friday` or `sunday`.

**Response**
```json
{
  "users": [
    { "discord_username": "someuser", "has_ride": false }
  ],
  "total": 10,
  "assigned": 7,
  "message_found": true,
  "has_coverage_entries": true
}
```

Unassigned users appear first; then alphabetically by username.

---

### `POST /api/check-pickups/sync`

Force-sync ride coverage by scanning recent channel messages for grouping assignments.

**Response**
```json
{
  "success": true,
  "message": "Ride coverage sync completed",
  "synced": 5,
  "errors": []
}
```

---

### `GET /api/check-pickups/driver-reactions/{day}`

Get emoji reactions from the driver chat message. `day` must be `friday` or `sunday`.

**Response**
```json
{
  "day": "friday",
  "reactions": { "👍": ["driver1"], "❌": ["driver2"] },
  "username_to_name": { "driver1": "First Last" },
  "message_found": true
}
```

---

## Group Rides

### `POST /api/group-rides`

Group ride requesters into cars using AI.

**Request body**
```json
{
  "ride_type": "friday",
  "message_id": null,
  "driver_capacity": "44444",
  "channel_id": "939950319721406464"
}
```

`ride_type` must be `friday`, `sunday`, or `message_id`. `driver_capacity` is a string of digits where each digit is the seat count for one driver (e.g. `"44444"` = 5 drivers with 4 seats each).

**Response**
```json
{
  "success": true,
  "summary": "5 drivers, 18 passengers",
  "groupings": [
    "Drive: @driver1 | @pass1 @pass2 @pass3 @pass4"
  ],
  "error": null
}
```

---

## Reaction Log

### `GET /api/reaction-log` — ride_coordinator

Get all logged reaction events (adds and removes) on ride announcement messages, grouped by message.

**Query params** (all optional)

| Param | Description |
|-------|-------------|
| `ride_type` | `friday`, `sunday`, `sunday_class`, or `wednesday` |
| `date_from` | ISO date — include rides on or after this date |
| `date_to` | ISO date — include rides on or before this date |
| `emoji` | Filter to a specific emoji string |

**Response**
```json
{
  "rides": [
    {
      "message_id": "123456",
      "ride_type": "friday",
      "ride_date": "2025-05-09",
      "label": "Friday · May 9, 2025",
      "events": [
        {
          "id": 1,
          "discord_username": "someuser",
          "display_name": "First Last",
          "emoji": "🪨",
          "action": "add",
          "occurred_at": "2025-05-07T14:30:00"
        }
      ]
    }
  ]
}
```

Rides are sorted newest first. `action` is `"add"` or `"remove"`.

---

### `GET /api/reaction-log/stream` — ride_coordinator

Server-Sent Events (SSE) stream of live reaction events. The connection stays open and emits a JSON frame for each new reaction. A heartbeat comment (`": heartbeat"`) is sent every 30 seconds to keep proxies alive.

Each data frame has the same shape as a single `ReactionEventOut` object from the reaction log, plus a `message_id` field.

---

## Miscellaneous

### `GET /api/usernames`

Get Discord username + display name pairs for @mention autocomplete.

**Response**
```json
{
  "users": [
    { "username": "someuser", "name": "First Last" }
  ]
}
```

---

### `GET /api/locations/pickups-by-message`

Get pickup locations from reactions on a specific Discord message.

**Query params**

| Param | Required | Description |
|-------|----------|-------------|
| `message_id` | Yes | Discord message ID |
| `channel_id` | No | Defaults to rides announcements channel |

**Response** — same shape as `/api/list-pickups` data.

---

### `POST /api/cache/invalidate` — admin

Invalidate all cache entries. Use after manual data changes.

**Response**
```json
{ "message": "All cache entries invalidated" }
```
