"""
Bot API Access Layer

This module provides access to the Discord bot instance for the FastAPI application.
It manages the bot lifecycle and allows API endpoints to interact with Discord.
"""

import asyncio
import logging
import os
import traceback
from contextlib import asynccontextmanager

import discord
from discord.ext.commands import Bot
from dotenv import load_dotenv

from bot.core.lifecycle import APP_ENV, attach_event_handlers, build_bot, load_extensions, startup

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")
_error_channel_id = os.getenv("ERROR_CHANNEL_ID")
ERROR_CHANNEL_ID: int | None = int(_error_channel_id) if _error_channel_id else None

if ERROR_CHANNEL_ID:
    logger.info(f"✅ Error channel configured: {ERROR_CHANNEL_ID}")
else:
    logger.warning("⚠️  Error channel not configured - errors will only be logged")

_bot_instance: Bot | None = None


def get_bot() -> Bot | None:
    """
    Get the running Discord bot instance.

    Returns:
        The bot instance if running and ready, None otherwise.
    """
    return _bot_instance if _bot_instance and _bot_instance.is_ready() else None


async def send_error_to_discord(
    error_msg: str, error: Exception | None = None, tb_text: str | None = None
) -> None:
    """
    Send an error message and optional traceback to the configured Discord error channel.
    If `error` is provided, it extracts the traceback directly from the Exception object.
    If neither `error` nor `tb_text` is provided, it attempts to extract the traceback
    from sys.exc_info().
    """
    if APP_ENV == "local" or ERROR_CHANNEL_ID is None:
        return

    bot = get_bot()
    if not bot:
        logger.warning("Could not send error to Discord: Bot is not ready")
        return

    if tb_text is None:
        if error is not None:
            tb_lines = traceback.format_exception(type(error), error, error.__traceback__)
            tb_text = "".join(tb_lines)
        else:
            import sys

            exc_info = sys.exc_info()
            if exc_info[0] is not None:
                tb_lines = traceback.format_exception(*exc_info)
                tb_text = "".join(tb_lines)

    try:
        channel = bot.get_channel(ERROR_CHANNEL_ID)
        if channel and isinstance(channel, discord.TextChannel):
            if tb_text and len(error_msg) + len(tb_text) > 1900:
                await channel.send(error_msg)
                chunks = [tb_text[i : i + 1900] for i in range(0, len(tb_text), 1900)]
                for chunk in chunks:
                    await channel.send(f"```python\n{chunk}\n```")
            else:
                full_msg = error_msg
                if tb_text:
                    full_msg += f"\n```python\n{tb_text}\n```"
                await channel.send(full_msg)
        else:
            logger.warning(f"Error channel {ERROR_CHANNEL_ID} not found or not a text channel")
    except Exception as e:
        logger.error(f"Failed to send error to Discord channel {ERROR_CHANNEL_ID}: {e}")


@asynccontextmanager
async def bot_lifespan():
    """
    Async context manager for Discord bot lifecycle.

    Handles bot initialization, startup, and shutdown.
    Sets the global _bot_instance for API access.

    Usage:
        async with bot_lifespan():
            # Bot is running
            pass
        # Bot is shutdown
    """
    global _bot_instance

    bot = build_bot()
    attach_event_handlers(bot, send_error_to_discord)
    _bot_instance = bot

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
        _bot_instance = None
        logger.info("✅ Discord bot shutdown complete")
