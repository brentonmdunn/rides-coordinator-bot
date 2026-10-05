# Slack announcements forwarding: internals

How the Slack → Discord bridge works under the hood. For setup and user-facing behavior, see
[slack-announcements.md](slack-announcements.md).

## Components

| Piece | File | Role |
|---|---|---|
| Cog | `backend/stonesbot/cogs/slack_announcements.py` | Owns the Slack connection: reads env, builds clients, connects on ready, acks requests, applies gates |
| Service | `backend/stonesbot/services/slack_forward_service.py` | All forwarding logic: dispatch, rendering, files, webhook, persistence |
| Formatter | `backend/stonesbot/utils/slack_format.py` | Pure functions: Slack mrkdwn → Discord markdown, message splitting |
| Repository | `backend/stonesbot/repositories/slack_forwarded_message_repository.py` | `slack_forwarded_messages` table access |
| Model | `SlackForwardedMessage` in `backend/shared/core/models.py` | Slack ts → Discord message id mapping |
| Flag | `FeatureFlagNames.SLACK_ANNOUNCEMENTS_FORWARDING` | Runtime on/off (seeded off by migration `43a03ddfa8a6`) |

Dependency: `slack-sdk` only (no Bolt). Its aiohttp Socket Mode client reuses the `aiohttp`
that discord.py already pulls in.

```
                      ┌──────────────────────── one Python process ────────────────────────┐
Slack ◀══ WSS ══════▶ │ SocketModeClient ──▶ SlackAnnouncements._on_request                │
 (Socket Mode)        │                         │ 1. ack envelope                          │
                      │                         │ 2. _forward  (@log_job_quiet,            │
                      │                         │    @bot_enabled, @feature_flag_enabled)  │
                      │                         ▼                                          │
Slack Web API ◀─HTTPS─│ AsyncWebClient ◀── SlackForwardService.handle_event (asyncio.Lock) │
 users.info, chat.   │   httpx (files)         │                                          │
 getPermalink, files │                         ├─▶ slack_format (pure)                    │
                      │                         ├─▶ discord.Webhook ─────HTTPS────────────▶│──▶ Discord channel
                      │                         └─▶ SlackForwardedMessageRepository ──▶ SQLite
                      └─────────────────────────────────────────────────────────────────────┘
```

---

## Lifecycle

1. **Cog load** (`cog_load`, during `load_extensions`, before Discord login). Reads
   `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` and `SLACK_ANNOUNCEMENTS_CHANNEL_ID`. If any is blank,
   it logs one warning and returns, leaving `socket_client`/`service` as `None`. The cog still
   counts as loaded, so `/health` isn't affected. Otherwise it builds:
   - `AsyncWebClient(token=SLACK_BOT_TOKEN, timeout=10)`, shared by the service and the
     socket client;
   - `SlackForwardService(..., discord_channel_id=resolve_channel_id(REFERENCES__CHURCH_ANNOUNCEMENTS))`.
     The channel is resolved **once** here, so `APP_ENV=local` sends everything to `#bots`;
   - `SocketModeClient(app_token=SLACK_APP_TOKEN)`, with `_on_request` registered as its
     request listener.
2. **Connect on `on_ready`.** It can't connect in `cog_load`: the bot hasn't logged in, so the
   target channel can't be resolved yet (and `wait_until_ready()` raises before login).
   `on_ready` fires again after every Discord reconnect, so it checks `is_connected()` first
   and only opens the socket once. Connect failures are logged and sent to the error channel.
3. **Running.** `slack-sdk` keeps the websocket alive (ping every 5s) and reconnects by itself
   (`auto_reconnect_enabled=True`), including when Slack rotates the connection, which it does
   every few hours.
4. **Unload** (`cog_unload`). Closes the client, wrapped in `asyncio.wait_for(..., 10s)` so an
   unreachable Slack can't block shutdown.

### Bot context

`current_bot_var` is set at the top of StonesBot's `run_bot` task. `on_ready` runs in a task
spawned from that task, and `SocketModeClient.connect()` spawns its receive loop from
`on_ready`. Each incoming message is then handled in a task created by `asyncio.ensure_future`
inside that loop. Context is copied at every `create_task`, so the event handlers still see
`STONESBOT`. That's what lets `@bot_enabled` find the right kill switch and lets
`BotNameFilter` tag the log lines.

---

## Event pipeline

### 1. Receive and acknowledge (`_on_request`)

Every Socket Mode request gets acknowledged **first**, unconditionally, by sending a
`SocketModeResponse(envelope_id=...)`. Slack resends unacknowledged envelopes after a few
seconds, so acknowledging before any slow work (Discord calls, file downloads) avoids
duplicate deliveries. Only `events_api` requests go further; anything else (e.g. slash
commands, if ever enabled) is acknowledged and dropped.

### 2. Gates (`_forward`)

```python
@log_job_quiet                      # fresh txn id; start/end logged at DEBUG
@bot_enabled                        # StonesBot kill switch
@feature_flag_enabled(SLACK_ANNOUNCEMENTS_FORWARDING, enable_logs=False)
async def _forward(self, event): ...
```

Every message in the Slack channel (joins, thread replies, edits) arrives as an event. So
"started/completed" logging is DEBUG, and blocked-by-flag isn't logged at all; otherwise a
disabled flag would log a line for every Slack message. Flags are read from
`FeatureFlagsRepository._cache`, so the gate costs no DB query.

### 3. Dispatch (`SlackForwardService.handle_event`)

Events are filtered on `type == "message"` and `channel == SLACK_ANNOUNCEMENTS_CHANNEL_ID`.
Then, under a single `asyncio.Lock`:

| `event.subtype` | Handler |
|---|---|
| `None`, `file_share`, `thread_broadcast` | `_forward_new(event)` |
| `message_changed` | `_forward_edit(event)` |
| `message_deleted` | `_forward_delete(event["deleted_ts"])` |
| anything else (`channel_join`, `bot_message`, `channel_topic`, …) | ignored (DEBUG log) |

**Why the lock:** `slack-sdk` handles each incoming message in its own task, so a quick
post-then-edit can be processed concurrently. Without serializing, the edit could look up the
mapping before the post had saved it and get skipped. Traffic is a few messages a week, so one
lock for the whole service costs nothing.

**Error boundary:** `handle_event` wraps everything in `try/except Exception`. It calls
`logger.exception` and `send_error_to_discord`, and never re-raises, so one bad event can't
break the listener.

---

## Flows

### New post (`_forward_new` → `_post` → `_send`)

1. **Skip** thread replies (`thread_ts` set, `!= ts`, and not `thread_broadcast`).
2. **Dedupe:** if `slack_forwarded_messages` already has rows for this ts, skip. This catches
   Slack redeliveries.
3. **Webhook:** `_get_webhook()` (see [Webhook](#webhook)). Returns early if unavailable.
4. **Author:** `users.info` → `profile.display_name`, else `real_name`, else `name`, else
   `"Slack"`. Avatar is `profile.image_192`. Cached in memory for 1 hour per user id. API errors
   fall back to `"Slack"` with no avatar and don't block the post.
5. **Files:** each file stub with `file_access == "check_file_info"` is expanded with
   `files.info`. Then `plan_files` sorts them (see [Files](#files)).
6. **Text:** `_render_text` resolves every `<@U…>` id to a display name (same author cache),
   runs `slack_to_discord`, appends the file notes as extra lines, then appends
   `-# [View in Slack](<permalink>)` from `chat.getPermalink` (no scope needed). `-#` is
   Discord's subtext markdown, and the angle brackets suppress the link preview. Because it's
   the final line, splitting always leaves it on the last part. A message with no text, notes
   or attachments renders as empty and isn't forwarded, so a bare link is never posted. If the
   permalink call fails, the line is just left off. Edits re-render the same way, so the link
   survives them.
7. **Send:** `_send` splits the text with `split_message` and sends each chunk with
   `webhook.send(username="<name> (via Slack)", avatar_url=..., allowed_mentions=none(), wait=True)`.
   Attachments go on the **last** chunk. With files but no text, one message holding just the link is
   sent. If a later chunk fails, the chunks already sent are deleted before re-raising, so no
   half-posted announcement is left behind.
8. **413 fallback:** if Discord rejects the request as too large (`HTTPException.status == 413`)
   and attachments were included, the post is retried with no files and a "too large" note for
   each one.
9. **Persist:** one `SlackForwardedMessage` row per sent message (`part = 0..n-1`), committed
   in one transaction.

### Edit (`_forward_edit`)

The event carries `message` (new state) and `previous_message` (old state); the ts is
`message.ts`.

1. `message.subtype == "tombstone"` → treated as a **delete**. Slack does this when you delete
   a message that has thread replies: the parent stays as a "This message was deleted."
   placeholder.
2. Thread replies → ignored.
3. No mapping rows → skip (the post predates the bridge, or was a thread reply).
4. Text unchanged **and** file ids unchanged → skip. Slack sends `message_changed` for reply
   counts, link unfurls, reactions to threads, etc.
5. Re-plan files and re-render text. `plan_files` depends only on metadata, so the same notes
   come out without downloading anything.
6. Split the new text, then:
   - **Same number of parts and same files** → `webhook.edit_message(id, content=chunk)` on each
     part. Attachments aren't passed, so Discord keeps the existing ones.
   - **Different number of parts or different files** → `_repost`: post the new version (full
     new-post path, files downloaded again), then delete the old Discord messages, then replace
     the mapping rows (delete + insert, one commit). New-before-old means a failed send never
     leaves the channel without the announcement. Reposting is simpler than in-place surgery:
     Discord can't insert a message mid-channel, and moving attachments between parts is
     fiddly.

### Delete (`_forward_delete`)

Look up the rows → `webhook.delete_message` each part (`NotFound` is logged and skipped) →
delete the rows and commit.

---

## Webhook

`_get_webhook()` lazily resolves and caches one `discord.Webhook`:

1. `bot.get_channel(discord_channel_id)` must be a `TextChannel`; otherwise log a warning and
   return `None`.
2. Scan `channel.webhooks()` for one named `Slack Announcements` whose `user.id` is StonesBot's
   and that has a token. Matching on the owner means a webhook someone else made with the same
   name is never used.
3. If none is found, call `channel.create_webhook(name="Slack Announcements")`.
4. `discord.Forbidden` (missing **Manage Webhooks**) → `logger.exception` plus an error-channel
   report naming the missing permission, and return `None`. The event is dropped.

Edits and deletes have to go through the **same** webhook that posted the message, which is
why it's found by name and owner, not recreated each run. The cache lives in memory only; after
a restart it's found again by the same scan.

`webhook_username`: `"<name> (via Slack)"`, trimmed to Discord's 80-character limit. Discord
rejects webhook usernames containing "discord" or "clyde", so those names fall back to
`"Slack announcement"`.

---

## Formatting (`slack_format.py`)

Slack sends `text` in mrkdwn. Modern messages also carry `blocks` (rich text), but `text` is
always present and accurate enough, so it's the only input.

`slack_to_discord(text, user_names)`:

1. **Protect.** One regex pass (`_PROTECTED_PATTERN`) finds fenced code (```` ``` ````), inline
   code (`` ` ``) and angle-bracket entities (`<...>`), in that order of preference. Each match
   is replaced with a placeholder `\x00N\x00` and saved:
   - code is saved verbatim;
   - entities are converted first (`_convert_entity`):
     | Slack | Discord |
     |---|---|
     | `<https://x\|label>` | `[label](https://x)` |
     | `<https://x>` | `https://x` |
     | `<mailto:a@b\|a@b>` | `a@b` |
     | `<@U123>` / `<@U123\|bob>` | `@<resolved name>` → `@bob` → `@unknown` |
     | `<#C123\|general>` | `#general` |
     | `<!channel>` `<!here>` `<!everyone>` | `@channel` `@here` `@everyone` (plain text) |
     | `<!subteam^S1\|@team>`, `<!date^…\|fallback>`, other `<!…>` | the label |
2. **Convert markers** on what's left: `*x*` → `**x**`, `~x~` → `~~x~~`. The regexes need a
   non-space right inside each marker and no word character or doubled marker right outside,
   so `2*3*4`, `snake_case`, `a * b` and already-doubled `**x**` are left alone. `_italic_`,
   `>` quotes and code already match Discord's syntax.
3. **Restore** the placeholders. Because they stood in during step 2, a `*` inside a URL or
   code span is never touched. Bold that wraps a link (`*see <url|here>*`) still works, because
   the placeholder counts as a non-space character.
4. **Unescape** `&amp;`, `&lt;`, `&gt;` (`html.unescape`). This comes last because Slack escapes
   these in user text and uses real `<>` only for entities.

`extract_user_ids(text)` lists the `<@U…>`/`<@W…>` ids so the service can resolve names before
calling the formatter, which keeps the formatter free of I/O.

`split_message(text, limit=2000)`: break into lines; split any line over the limit at spaces,
and hard-cut any single word over the limit; then pack the pieces back together greedily,
joined by `\n`. Whitespace-only chunks are dropped. A code block that crosses a chunk boundary
will render oddly. That's accepted, since announcements rarely run past 2000 characters.

---

## Files

`plan_files(files, size_limit)` decides from metadata only:

| File | Result |
|---|---|
| `mode == "tombstone"` (file deleted) | dropped silently |
| `mode == "external"` (Drive, Dropbox, …) | note line `📎 [name](url)` |
| `size > guild.filesize_limit` | note line `📎 name (too large to attach here, see Slack)` |
| beyond the 10th attachable file | same "too large" note |
| otherwise | attached |

`_download_files` fetches each attached file from `url_private_download` (falling back to
`url_private`) using `httpx.AsyncClient(timeout=30, follow_redirects=True)` and
`Authorization: Bearer <SLACK_BOT_TOKEN>`. Files are buffered in memory (bounded by the guild
upload limit) and wrapped in `discord.File`.

**Missing-scope trap:** without `files:read`, Slack doesn't return 403. It returns **200 with
its HTML sign-in page**. If the response is `text/html` and the file's `filetype` isn't html,
`_download_files` raises a `RuntimeError` naming the `files:read` scope, so the error is
obvious and no login page gets uploaded as `flyer.png`.

The upload limit is `channel.guild.filesize_limit` (it depends on the server's boost tier),
falling back to discord.py's 10 MiB default. Discord can still reject a message whose combined
attachments are too big; that's what the 413 fallback is for.

---

## Data model

```
slack_forwarded_messages
  id                  INTEGER PK
  slack_channel_id    TEXT       ┐
  slack_ts            TEXT  (ix) ├ UNIQUE
  part                INTEGER    ┘  0-based index among a post's Discord messages
  discord_channel_id  TEXT
  discord_message_id  TEXT
  created_at          DATETIME  default CURRENT_TIMESTAMP
```

- A Slack message's `ts` (e.g. `1728000000.123456`) is its id within a channel, so the key is
  `(slack_channel_id, slack_ts)`.
- The unique constraint on `part` backs up the dedupe check: even if two deliveries got past
  the lock-protected check, the second insert would fail.
- Rows are never pruned. At a few announcements a week the table stays tiny, and keeping every
  row means old posts stay editable and deletable.

The repository follows the repo conventions (static methods, session as first argument, no
commits). The service owns the unit of work: `_get_parts` expunges the rows before closing
their session, and `_save_parts` does delete + insert + commit in one session.

---

## Failure modes

| Failure | What happens |
|---|---|
| Slack env var missing | One startup warning; cog idles; rest of the app unaffected |
| Bad Slack token / Slack unreachable at startup | `connect()` raises → logged + error-channel report; no retry until the next process start |
| Websocket drops later | `slack-sdk` reconnects automatically; events sent during the gap are lost |
| Flag or kill switch off | Requests still acked; events dropped silently |
| StonesBot lacks Manage Webhooks | Error-channel report naming the permission; event dropped |
| `users.info` fails | Posted as `Slack (via Slack)` with no avatar |
| `chat.getPermalink` fails | Posted without the View in Slack line |
| File download fails / missing `files:read` | Whole event fails → logged + reported; nothing posted |
| Discord 413 on attachments | Reposted without files, with notes |
| Discord error mid-split | Already-sent parts deleted; error reported |
| Discord message already deleted by a mod | Edit/delete logs it and continues |
| Two environments share the Slack app token | Slack splits events between them; each sees only some (avoid; see setup doc) |
| Webhook deleted in Discord | New one created on next post; older messages can't be edited/deleted anymore |

---

## Tests

| File | Covers |
|---|---|
| `tests/unit/test_slack_format.py` | Every conversion, protection of code/URLs, mention fallbacks, splitting bounds |
| `tests/unit/test_slack_forward_service.py` | Dispatch, thread/subtype filtering, dedupe, splitting, mentions, file plan + notes, 413 retry, partial-send cleanup, webhook reuse/creation/Forbidden, in-place edit vs repost, tombstones, deletes, sign-in-page detection |
| `tests/unit/test_slack_forwarded_message_repository.py` | Real in-memory SQLite: ordering, channel scoping, delete scope, unique constraint |
| `tests/unit/test_slack_announcements_cog.py` | Env handling, local channel routing, connect-once, connect-failure reporting, ack-then-forward, flag gating |
