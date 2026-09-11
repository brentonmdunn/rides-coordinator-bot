"""
Bot API Access Layer

This module provides the bot lifecycle context manager for the FastAPI application.
Bot instance access is in shared.core.bot_instance; error reporting is in shared.core.error_reporter.
"""

import asyncio
import contextlib
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from shared.core.bot_instance import get_bot
from shared.core.bots import resolve_enabled_bots
from shared.core.lifecycle import close_bot, run_bot, startup

logger = logging.getLogger(__name__)

load_dotenv()

_READY_POLL_INTERVAL_SECONDS = 0.1


@asynccontextmanager
async def bot_lifespan():
    """
    Async context manager for Discord bot lifecycle.

    Handles bot initialization, startup, and shutdown for every enabled bot.
    Sets the global bot instances for API access.

    Usage:
        async with bot_lifespan():
            # Bots are running
            pass
        # Bots are shutdown
    """
    if os.getenv("DISABLE_DISCORD_BOT", "").lower() == "true":
        logger.warning(
            "DISABLE_DISCORD_BOT=true — running in API-only mode, bots and all scheduled jobs are disabled"
        )
        yield None
        return

    enabled_bots = resolve_enabled_bots()

    try:
        await startup()
    except Exception:
        logger.exception("Startup failed")
        sys.exit(1)

    tasks = {
        enabled.spec.name: asyncio.create_task(
            run_bot(enabled.spec, enabled.token), name=f"bot:{enabled.spec.name}"
        )
        for enabled in enabled_bots
    }

    try:
        while not all(get_bot(name) is not None for name in tasks):
            done = [name for name, task in tasks.items() if task.done()]
            if done:
                for name in done:
                    task = tasks[name]
                    exc = task.exception()
                    if exc is not None:
                        logger.error(
                            f"[{name}] Bot task failed before becoming ready", exc_info=exc
                        )
                    else:
                        logger.error(f"[{name}] Bot task exited before becoming ready")
                sys.exit(1)
            await asyncio.sleep(_READY_POLL_INTERVAL_SECONDS)

        logger.info("🤖 All Discord bots are ready and connected!")
        yield None

    finally:
        logger.info("🛑 Shutting down Discord bots...")
        await asyncio.gather(*(close_bot(name) for name in tasks), return_exceptions=True)
        for task in tasks.values():
            task.cancel()
        for task in tasks.values():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        logger.info("✅ Discord bot shutdown complete")
