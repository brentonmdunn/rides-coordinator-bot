# Logging Conventions

## Setup

- Logging is configured in `bot/core/logger.py`. It sets up the root logger with console + rotating file handlers.
- Every file uses its own per-module logger:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- **Never** use `from bot.core.logger import logger` — that's the root logger. Always create a per-module logger with `getLogger(__name__)`.
- **Never** use `print()` for diagnostics — always use `logger`.

## Log Levels

| Level | When to use |
|-------|-------------|
| `DEBUG` | Detailed diagnostic info only useful during development (variable values, intermediate state, cache hits) |
| `INFO` | Normal operational events: startup, shutdown, sync completion, commands invoked, successful operations |
| `WARNING` | Recoverable problems or expected-but-notable conditions: bot not ready, missing optional config, network timeouts, invalid user input in API routes |
| `ERROR` | Failures that affect a specific operation but don't crash the app (use sparingly — prefer `exception` in `except` blocks) |
| `CRITICAL` | App-wide failures (rarely used) |

## Exception Logging

- **In `except` blocks, always use `logger.exception("message")`** — it automatically appends the full traceback. Never use `logger.error(f"...{e}")` in an except block; the traceback will be missing.
- **Do NOT include the exception in the format string** — `logger.exception` already includes it:
  ```python
  # ✅ Correct
  except Exception:
      logger.exception("Failed to sync locations")

  # ❌ Wrong — redundant, prints exception twice
  except Exception as e:
      logger.exception(f"Failed to sync locations: {e}")

  # ❌ Wrong — no traceback
  except Exception as e:
      logger.error(f"Failed to sync locations: {e}")
  ```
- **Never silently swallow exceptions.** If an `except` block returns a default value, still log the exception:
  ```python
  except Exception:
      logger.exception("Failed to check coverage status")
      return False
  ```

## Transaction IDs & Context

- Slash commands: wrap with `@log_cmd` (from `bot.core.logger`) to auto-assign a transaction ID and log the command invocation.
- Scheduled jobs: wrap with `@log_job` to auto-assign a transaction ID.
- API requests: transaction IDs are injected via `api/middleware/access_logger.py`.
- Log format includes `[txn:%(txn_id)s]` and `[%(user_email)s]` for tracing.

## Log Format

```
%(asctime)s %(levelname)-8s [txn:%(txn_id)s] [%(name)s:%(lineno)d] [%(user_email)s] %(message)s
```

- `%(name)s` shows the full module path (e.g., `bot.services.locations_service`), so there's no need to prefix messages with the module name manually.

## Common Patterns

- **Cog/command entry points**: Log at `INFO` with user-relevant context (command name, arguments, day, message_id).
- **Service operations**: Log start/completion at `INFO`; intermediate steps at `DEBUG`.
- **Repository queries**: Generally no logging needed for routine queries. Log exceptions and unusual conditions.
- **Bot not ready / missing optional config**: Use `WARNING`, not `ERROR`.
- **Sending errors to Discord**: Always pair `logger.exception(...)` with `await send_error_to_discord(...)` for unexpected errors in user-facing flows.
