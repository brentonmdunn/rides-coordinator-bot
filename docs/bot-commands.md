# Discord Bot Commands

All commands are Discord slash commands (`/command-name`). Most commands are guarded by the `bot` feature flag — if that flag is disabled, the command silently does nothing.

Commands are restricted to whitelisted channels. Attempting a command in a non-whitelisted channel produces an ephemeral error.

---

## Locations

### `/list-pickups-friday`

List all pickup locations for the upcoming Friday fellowship, derived from emoji reactions on the current week's announcement message.

### `/list-pickups-sunday`

List all pickup locations for the upcoming Sunday service.

### `/list-dropoffs-sunday-back`

List dropoff locations for users returning straight home after Sunday service (no lunch).

### `/list-dropoffs-sunday-lunch`

List dropoff locations for users staying for lunch.

### `/list-pickups-by-message-id`

List pickups from a specific Discord message ID.

| Param | Required | Description |
|-------|----------|-------------|
| `message_id` | Yes | Discord message ID |
| `channel_id` | No | Channel ID (defaults to rides announcements channel) |

### `/pickup-location`

Look up the stored pickup location for a specific person.

| Param | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Name or Discord username |

### `/sync-locations`

Sync the Google Sheets location data into the database. Run after updating the sheet.

### `/map-links`

Post Google Maps links for pickup locations. Optionally filter by location name.

| Param | Required | Description |
|-------|----------|-------------|
| `location` | No | Partial location name to filter by |

---

## Group Rides (AI Grouping)

These commands use a GenAI model to group riders with available drivers.

### `/group-rides-friday`

Group riders and drivers for Friday fellowship.

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `driver_capacity` | No | `"44444"` | String of digits — each digit is one driver's seat count |
| `custom_prompt` | No | — | Override the default prompt |
| `legacy_prompt` | No | `false` | Use the older prompt format |

### `/group-rides-sunday`

Group riders and drivers for Sunday service. Same parameters as `/group-rides-friday`.

### `/group-rides-by-message-id`

Group riders using a specific message ID.

| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `message_id` | Yes | — | Discord message ID to fetch pickups from |
| `driver_capacity` | No | `"44444"` | Same format as above |
| `legacy_prompt` | No | `false` | |

### `/make-route`

Generate a formatted route string from a list of pickup locations.

| Param | Required | Description |
|-------|----------|-------------|
| `locations` | Yes | Space-separated pickup location keys (e.g. `SEVENTH ERC MARSHALL`) |
| `leave_time` | Yes | Departure time (e.g. `7:10pm`) |

Outputs the formatted route as a Discord message and in a code block.

---

## Ask Drivers

### `/ask-drivers`

Ping the driver role in the driver chat channel with a custom message. The bot automatically adds reaction emojis to the message.

| Param | Required | Description |
|-------|----------|-------------|
| `day` | Yes | `Friday` or `Sunday` (autocompleted) |
| `message` | Yes | Message body |

Only works in the driver chat channel or bot testing channels.

---

## Non-Discord Rides

For users who need a ride but are not on Discord.

### `/add-pickup`

Add a pickup entry for a non-Discord user.

| Param | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Person's name |
| `day` | Yes | Day of pickup (autocompleted) |
| `location` | Yes | Pickup location (autocompleted) |

Returns an ephemeral error if the entry already exists.

### `/remove-pickup`

Remove a pickup entry for a non-Discord user.

| Param | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Person's name |
| `day` | Yes | Day to remove (autocompleted) |

### `/list-added-pickups`

List all non-Discord user pickups for a given day.

| Param | Required | Description |
|-------|----------|-------------|
| `day` | Yes | Day to list (autocompleted) |

---

## Threads

These commands must be run inside a Discord thread.

### `/create-event-thread`

Mark the current thread as an "event thread." Anyone who reacts to the thread's parent message will be automatically added to the thread.

Adds all existing reactors immediately. Also prints a note about the `event_threads` feature flag.

### `/end-event-thread`

Stop the auto-add behavior for the current thread.

### `/add-reacts-to-thread`

Manually add all current reactors on the parent message to the thread. Useful if the bot was offline when reactions were added.

---

## Feature Flags

### `/feature-flag`

Enable or disable a feature flag.

| Param | Required | Description |
|-------|----------|-------------|
| `feature_name` | Yes | Flag name (autocompleted) |
| `enabled` | Yes | `True` or `False` |

### `/list-feature-flags`

Display all feature flags and their current state as an embed.

---

## Admin

These commands require the `Manage Roles` or `Manage Channels` permission.

### `/give-role`

Assign a Discord role to one or more users by username.

| Param | Required | Description |
|-------|----------|-------------|
| `role` | Yes | The Discord role to assign |
| `discord_usernames` | Yes | Space- or comma-separated Discord usernames |

### `/add-to-channel`

Grant read/write access to the current channel for one or more users.

| Param | Required | Description |
|-------|----------|-------------|
| `discord_usernames` | Yes | Space-separated Discord usernames |

---

## Other

### `/whois`

Search for a user by name and get their Discord username.

| Param | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Name to search |

### `/help`

Shows all available slash commands as an ephemeral embed. Useful for discovering what the bot supports.

---

## Disabled commands

The following cogs are currently in `bot/cogs_disabled/` and are not loaded:

- **infra** — Infrastructure/server management commands.
- **retreat** — Retreat-specific ride coordination commands.
