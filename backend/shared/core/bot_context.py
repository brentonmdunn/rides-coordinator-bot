"""Tracks which bot the current asyncio task belongs to."""

from contextvars import ContextVar

from shared.core.enums import BotName

# Set as the first statement of each bot's run task; child tasks (event handlers,
# app commands, APScheduler callbacks) inherit it because asyncio copies context.
current_bot_var: ContextVar[BotName | None] = ContextVar("current_bot", default=None)


def get_current_bot_name() -> BotName | None:
    """Return the bot running the current task, or None outside any bot (e.g. API requests)."""
    return current_bot_var.get()
