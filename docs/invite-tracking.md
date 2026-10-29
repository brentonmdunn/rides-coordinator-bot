# Invite tracking

StonesBot posts new member joins to **serving → #server-admin-bot-spam** (channel ID
`1565258920342069291`). The invite tracking extension is owned only by StonesBot;
RideBot does not load it, including when running by itself.

StonesBot needs **Manage Server** to fetch invite usage, **View Channel** and
**Send Messages** in #server-admin-bot-spam, and the **Server Members Intent** enabled in the Discord
developer portal (the code already requests it). **Manage Channels** on invite
channels allows Discord's invite creation events to keep new links in the cache.
Without creation events, a new link's first observed use is reported as unknown.

Example post:

> 👋 @Alex joined **Our server**. Likely invite creator: @Jamie (invite `abc`).

Mentions display identities without sending notifications. The creator is the
account that made the link; someone else may have shared it. Attribution is
inferred from a single usage count increasing by one, rather than a direct
Discord record connecting a member to an invite.

When usage changes are ambiguous, an invite disappears (including consumed
single-use links), no baseline exists, or invite lookup fails, the join is still
posted with an unknown creator. Simultaneous joins can be impossible to attribute
accurately. Vanity links and other join methods without a regular invite match
also produce unknown attribution.

Usage snapshots are kept in memory. Startup and reconnects establish a fresh
baseline; the bot does not reconstruct historical joins or replay events missed
while offline. Published messages remain in #server-admin-bot-spam. No database migration or new
environment variables are required.

Local development (`APP_ENV=local`) redirects outbound messages to #bots.
