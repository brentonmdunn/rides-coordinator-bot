# Slack announcements forwarding

StonesBot mirrors the church Slack's **#announcements** channel into Discord's church
announcements channel. New posts, edits, deletes and attachments carry over; thread replies
don't.

```
Slack #announcements ──(Socket Mode websocket, outbound)──▶ StonesBot
   new / edited / deleted message events                      │
                                                              ├─ Slack Web API: author name/avatar, files
                                                              ├─ Slack mrkdwn → Discord markdown
                                                              ├─ "Slack Announcements" webhook ──▶ Discord channel
                                                              └─ slack_forwarded_messages (Slack ts → Discord ids)
```

- **Two identities.** The Slack app only *reads* Slack. Everything on the Discord side is
  StonesBot: it finds or creates a webhook named `Slack Announcements` in the target channel and
  posts through it, so each message shows the Slack author's name and avatar
  (`Jane Doe (via Slack)`).
- **No public endpoint.** Socket Mode is an outbound websocket from our server, so nothing has
  to get past Cloudflare Access or the session middleware.
- **Link back.** Every forwarded post ends with a subtext `View in Slack` link to the original
  message (the church Slack is open to everyone, so anyone can follow it).
- **Pings are opt-in.** By default `@channel`, `@here` and `@everyone` come through as plain
  text and ping no one. With the `slack_announcements_pings` flag on, Slack's
  `@channel`/`@everyone` pings Discord's `@everyone` and `@here` pings `@here`. That happens
  only when a post is first forwarded, never on edits. `@Name` mentions never ping. Since
  anyone who can post in Slack #announcements can then ping the whole Discord server, only
  turn it on if posting there is restricted.
- **Target channel.** `ChannelIds.REFERENCES__CHURCH_ANNOUNCEMENTS`, resolved through
  `resolve_channel_id`. With `APP_ENV=local` that's `#bots`.

For how it works under the hood, see [slack-announcements-internals.md](slack-announcements-internals.md).

Code: `backend/stonesbot/cogs/slack_announcements.py` (connection),
`backend/stonesbot/services/slack_forward_service.py` (logic),
`backend/stonesbot/utils/slack_format.py` (formatting).

---

## Setup

Order matters: Slack app → Discord permission → server env → deploy → flag.

### 1. Create the Slack app (needs a Slack workspace admin)

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**, pick the
   church workspace, and paste:

   ```yaml
   display_information:
     name: Discord Bridge
     description: Forwards #announcements to the church Discord server.
   features:
     bot_user:
       display_name: Discord Bridge
       always_online: false
   oauth_config:
     scopes:
       bot:
         - channels:history
         - users:read
         - files:read
   settings:
     event_subscriptions:
       bot_events:
         - message.channels
     socket_mode_enabled: true
     org_deploy_enabled: false
     token_rotation_enabled: false
   ```

   If #announcements is a **private** channel, also add `groups:history` to the scopes and
   `message.groups` to the bot events.

2. **Basic Information → App-Level Tokens → Generate Token and Scopes**, add the
   `connections:write` scope. The `xapp-...` token is `SLACK_APP_TOKEN`.
3. **Install App → Install to Workspace.** The **Bot User OAuth Token** (`xoxb-...`) is
   `SLACK_BOT_TOKEN`.
4. In Slack, open #announcements and run `/invite @Discord Bridge`. The app only receives
   events from channels it's a member of.
5. Open the channel's details; the channel ID (`C...`) is at the bottom of the **About** tab.
   That's `SLACK_ANNOUNCEMENTS_CHANNEL_ID`.

### 2. Discord permission

Give StonesBot **Manage Webhooks** in the church announcements channel (and in `#bots` for
local testing). **Manage Messages** there is recommended too: it lets StonesBot clean up
forwarded posts itself if the webhook is ever deleted. Without it, the first forwarded message fails and reports
"StonesBot needs the Manage Webhooks permission" to the error channel.

### 3. Server env and deploy

Add the three `SLACK_*` vars to **one** environment's env file (normally `.env.prod`) and
deploy. The migration creates `slack_forwarded_messages` and seeds the flag **off**.

> **Only one environment may hold the Slack tokens.** Slack load-balances Socket Mode events
> across every open connection for the same app, so if preprod and prod (or your laptop) both
> connect, each one only sees some of the messages. For local testing, create a second Slack
> app in a test workspace and use its tokens.

On startup, look for `Connected to Slack for announcements forwarding` in the logs. If any var
is missing you'll see `Slack announcements forwarding disabled; missing ...` instead, and the
rest of the app runs normally.

### 4. Turn it on

Enable the `slack_announcements_forwarding` feature flag in the admin UI. Events received while
it's off are dropped, not queued.

Optionally, enable `slack_announcements_pings` so Slack's `@channel`/`@here` ping in Discord.
This also needs StonesBot to have **Mention Everyone** in the announcements channel; without
it the post still goes out but doesn't ping. Test it in `#bots` first.

---

## Behavior

| Slack | Discord |
|---|---|
| New top-level post | Posted via the webhook as `<name> (via Slack)`, ending with a small grey **View in Slack** link to the original (no link preview) |
| Reply in a thread | Ignored, unless sent with "Also send to #announcements" |
| Edit | Edited in place. If the edit changes the number of 2000-char parts or the attached files, the new version is posted and the old one deleted. |
| Delete | Deleted (a message that's already gone in Discord is skipped) |
| Discord moderator deletes the forwarded copy | Stays deleted; later Slack edits to it are ignored |
| Joins, topic changes, bot/workflow posts | Ignored |
| `*bold*`, `~strike~`, `<url\|text>` | `**bold**`, `~~strike~~`, `[text](url)` |
| `<@U123>`, `<#C123\|general>` | `@Name`, `#general` as plain text (no ping) |
| `@channel`, `@everyone`, `@here` | Plain text by default; with `slack_announcements_pings` on, `@everyone`/`@here` that ping (first forward only) |
| Files | Downloaded and re-uploaded, up to 10 per message and the server's upload limit. Anything else becomes a `📎 name (too large to attach here, see Slack)` line; externally hosted files (Google Drive, etc.) become a link. |
| Message over 2000 characters | Split at line breaks into several Discord messages; attachments go on the last |

## Limits

- Posts made before the app was set up aren't backfilled, and edits/deletes of them are ignored.
- Events sent while the app is down (or while the flag is off) are lost. Slack only retries
  briefly, and Socket Mode doesn't replay missed events.
- If the `Slack Announcements` webhook is deleted, StonesBot creates a new one on the next post.
  Edits to older posts then repost them (a webhook can't edit another webhook's messages), and
  deleting them needs StonesBot's Manage Messages.
- The webhook's name and avatar are a display label only; they don't link to a Discord account.
