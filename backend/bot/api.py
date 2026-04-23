"""
Bot API Access Layer

This module provides the bot lifecycle context manager for the FastAPI application.
Bot instance access is in bot.core.bot_instance; error reporting is in bot.core.error_reporter.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from bot.core.bot_instance import set_bot_instance
from bot.core.error_reporter import send_error_to_discord
from bot.core.lifecycle import APP_ENV, attach_event_handlers, build_bot, load_extensions, startup

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")


@asynccontextmanager
async def bot_lifespan():
    """
    Async context manager for Discord bot lifecycle.

    Handles bot initialization, startup, and shutdown.
    Sets the global bot instance for API access.

    Usage:
        async with bot_lifespan():
            # Bot is running
            pass
        # Bot is shutdown
    """
    bot = build_bot()
    attach_event_handlers(bot, send_error_to_discord)
    set_bot_instance(bot)

    await startup()

    if APP_ENV != "local":
        await load_extensions(bot)

    bot_task = asyncio.create_task(bot.start(TOKEN))

    try:
        while not bot.is_ready():
            await asyncio.sleep(0.1)

        logger.info("🤖 Discord bot is ready and connected!")
        yield bot

    finally:
        logger.info("🛑 Shutting down Discord bot...")
        await bot.close()
        await bot_task
        set_bot_instance(None)
        logger.info("✅ Discord bot shutdown complete")
