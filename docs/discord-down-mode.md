# Discord-Down Mode

When Discord is unavailable (outage, rate limiting, maintenance), you can run the API without the bot to keep the dashboard accessible on cached data.

## How it works

Setting `DISABLE_DISCORD_BOT=true` causes `bot_lifespan()` in `bot/api.py` to skip bot startup entirely and yield immediately. This means:

- No gateway connection attempt
- No rate-limit retries against Discord's API
- All APScheduler jobs are skipped (they are loaded via `load_extensions(bot)`, which is never called)
- The FastAPI server starts immediately instead of blocking on `while not bot.is_ready()`
- The API serves whatever is currently in the SQLite cache

## How to enable

Add `DISABLE_DISCORD_BOT=true` to your environment and restart the server.

**Docker / env file:**
```
DISABLE_DISCORD_BOT=true
```

**Shell:**
```bash
DISABLE_DISCORD_BOT=true uv run python run_api.py
```

## What still works

- All read endpoints that return cached data (pickups, reactions, usernames, locations, feature flags, etc.)
- The dashboard UI
- Auth (local mock or session cookies — no Discord OAuth round-trip needed for already-logged-in sessions)

## What stops working

- Any endpoint that calls the live Discord bot instance (`bot_instance.get_bot()` will return `None`)
- Sending ask-rides messages
- Real-time reaction updates from Discord
- Scheduled jobs (ask rides, cache refresh, etc.)

## Re-enabling

Remove `DISABLE_DISCORD_BOT` (or set it to anything other than `true`) and restart. The bot will reconnect normally.
