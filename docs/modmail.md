# Modmail

Two-way DM relay between Discord users and bot staff. Each user gets a private,
staff-only channel that mirrors every message in both directions, plus a simple
programmatic API any cog can call to DM a user.

## Quick start

1. Create a Discord category for modmail channels (e.g. `📬 Modmail`).
2. Set the env var:
   ```env
   MODMAIL_CATEGORY_ID=123456789012345678
   ```
3. Enable the feature flag:
   - via the existing feature-flag tooling, or
   - directly in the DB: `UPDATE feature_flags SET enabled=1 WHERE feature='modmail';`
4. Restart the bot.

That's it — the cog auto-registers, the listener picks up DMs, and `/dm` becomes
available to ride coordinators.

## How it works

### Inbound DM (user → bot)
1. The user opens the bot's profile and DMs it.
2. `Modmail.on_message` fires (`message.guild is None`).
3. The service finds the user's modmail channel in `MODMAIL_CATEGORY_ID`, or
   creates one named `dm-<sanitized-username>-<user-id>`.
4. The DM is mirrored into that channel as a green embed (content, attachments,
   timestamp, author info).

### Outbound (staff message in channel → user DM)
1. A non-bot member posts a message inside a modmail channel.
2. `Modmail.on_message` (guild path) fast-paths: it returns immediately unless
   the channel's `category_id` matches `MODMAIL_CATEGORY_ID`.
3. The service looks up the matching user, DMs them the message and any
   attachments, then replaces the staff message with a confirmation embed so
   the channel reads as a clean transcript.
4. If the user has DMs closed, a red ⚠️ embed is posted instead and the staff
   message is preserved.

### Programmatic DM (`dm_user`)
Any cog or scheduled job can DM a user with full mirror visibility:

```python
modmail = self.bot.get_cog("Modmail")
result = await modmail.dm_user(member_or_id_or_username, "hello")
if not result.delivered:
    # fall back to a public ping, mark them as unreachable, etc.
    ...
```

## Commands

| Command | Who can run it | What it does |
|---|---|---|
| `/dm user:<member> message:<text>` | RIDE_COORDINATOR role + admins | Sends a DM to `user` and mirrors the outgoing message in their modmail channel. Creates the channel if it doesn't exist. |

There is no `/close-modmail` — channels persist per user permanently. If a
channel is deleted manually, the next DM (in either direction) creates a new
one and the DB row is regenerated.

## Public methods

All on `bot.services.modmail_service.ModmailService` (and exposed via the
`Modmail` cog as `bot.get_cog("Modmail").dm_user(...)`).

### `dm_user(who, message, *, initiator=None, guild=None) -> DMResult`
DM a user and mirror the outgoing message in their modmail channel.

- `who` accepts:
  - a `discord.User` / `discord.Member` instance
  - a user ID as `int` or numeric `str`
  - a username `str` (matched across the bot's guild members; raises
    `ModmailAmbiguousUserError` if multiple users share the name)
- `message`: text content to send
- `initiator`: optional staff member shown as the sender in the mirror embed.
  Defaults to the bot itself.
- `guild`: optional override for which guild to create the channel in. Falls
  back to the bot's only guild when the bot is in exactly one guild.

**Does not raise on delivery failure.** If the user has DMs closed or has
blocked the bot, the method posts a ⚠️ embed in the mirror channel and returns
`DMResult(channel, delivered=False)`. Callers can branch on `result.delivered`
to decide on fallbacks.

Raises (caller-correctable issues only):
- `ModmailUserNotFoundError` — `who` couldn't be resolved
- `ModmailAmbiguousUserError` — username matched multiple users
- `ModmailConfigError` — `MODMAIL_CATEGORY_ID` missing/invalid

### `resolve_user(who) -> discord.abc.User`
Stand-alone resolver if you want to look up a user without sending anything.

### `get_or_create_channel(user, *, guild=None) -> discord.TextChannel`
Returns the modmail channel for a user, creating it if necessary. Useful if
you want to post into the channel without sending a DM (e.g., logging a
non-DM event into the conversation transcript).

### `relay_dm_to_channel(message)` / `relay_channel_to_dm(message)`
Internal hooks driven by `on_message`. Not normally called directly.

## Data model

Single table, one row per user:

```sql
modmail_channels (
    user_id     TEXT PRIMARY KEY,
    channel_id  TEXT UNIQUE NOT NULL,
    username    TEXT,
    created_at  TIMESTAMP DEFAULT now()
);
```

Migration: `alembic/versions/c9f7a2b4e011_add_modmail_channels.py`.

## Configuration

| Env var | Required | Description |
|---|---|---|
| `MODMAIL_CATEGORY_ID` | yes | Discord category ID where per-user channels are created. Without it, every modmail entry point errors out explicitly. |

| Feature flag | Default | Effect |
|---|---|---|
| `modmail` | disabled | Gates the `on_message` listener and `/dm` command. |

Channel permissions are computed at create time:
- `@everyone` → no read access
- `RIDE_COORDINATOR` role → read + send
- Every role with the `Administrator` permission → read + send

The DM'd user does NOT have access to their own modmail channel.

## Major design decisions

### Per-user channels, not threads
Threads are cheaper to spin up but harder to permission individually and
visually less obvious in the channel list. Channels in a dedicated category
give staff a sortable, searchable inbox.

### No "open/close" ticket lifecycle
The user said no tickets. Mappings are permanent: one row per user forever.
This is simpler and means a DM-driven bot interaction always lands in the
same channel. If a channel is deleted manually, the row is automatically
re-created on next contact.

### Permanent record on delivery failure
`dm_user` posts the outgoing-message embed into the channel **before** trying
to deliver. If delivery fails, a ⚠️ "Not delivered" embed is appended.
Result: staff always have a record of attempts, even when Discord refuses
delivery. The method does not raise for delivery failures — instead it returns
a `DMResult(channel, delivered)` so callers can branch.

### Fast-path on hot listener
`Modmail.on_message` runs on every guild message in every channel. Before any
DB lookup, it checks `channel.category_id == MODMAIL_CATEGORY_ID` and returns
early if not — keeping the listener cheap on a busy server.

### Single-guild assumption with explicit fallback
For "find or create channel" the service assumes exactly one guild. If the bot
is added to more, callers must pass an explicit `guild=...`. This avoids
silently creating duplicate channels in the wrong guild.

### Username resolution favors safety
Looking up users by username scans all guild members the bot has cached; if a
name matches multiple members, the resolver raises rather than guessing. Pass
a user ID (int) when in doubt.

### Slash command gated on RIDE_COORDINATOR (not raw permissions)
`/dm` uses the role-based `is_ride_coordinator()` decorator (see
`bot/utils/checks.py`) instead of `manage_channels`. Admins are allowed through
as a fallback. This ties access to the "ride coordinator" hat, not Discord
moderation perms.

### Layering: Cog → Service → Repository
Same as the rest of the codebase. The cog only handles command/listener
plumbing; all behavior lives in `ModmailService`; SQL lives in
`ModmailRepository`. Tests target the service-level helpers and the resolver.

## Files

| Path | What it is |
|---|---|
| `backend/bot/cogs/modmail.py` | Cog: `on_message` listener + `/dm` slash command + cog-level `dm_user(...)` shim. |
| `backend/bot/services/modmail_service.py` | All behavior: channel lifecycle, DM relay, user resolution, permission overwrites, exceptions, `DMResult`. |
| `backend/bot/repositories/modmail_repository.py` | DB access for `modmail_channels`. |
| `backend/bot/core/models.py` | `ModmailChannels` table. |
| `backend/bot/core/enums.py` | `FeatureFlagNames.MODMAIL`. |
| `backend/alembic/versions/c9f7a2b4e011_add_modmail_channels.py` | Migration. |
| `backend/tests/unit/test_modmail_service.py` | Unit tests for helpers + resolver. |

## Troubleshooting

- **"MODMAIL_CATEGORY_ID is not set"** — set the env var to a real category ID.
- **"… is not a category in guild '<name>'"** — the ID points to a non-category
  channel or a channel in a different guild.
- **`/dm` says "❌ Username 'foo' matches N users"** — pass a user ID instead.
- **DMs not arriving** — check the user hasn't disabled "Allow direct messages
  from server members" in the relevant guild, hasn't blocked the bot, and
  shares at least one server with the bot.
- **Listener doesn't fire on inbound DMs** — Message Content Intent + DM
  Messages Intent must be enabled in the Discord developer portal and the bot
  intents config.
