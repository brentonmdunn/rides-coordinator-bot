"""Main entry point for the bot."""

import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from bot.core.bot_instance import set_bot_instance
from bot.core.error_reporter import send_error_to_discord
from bot.core.lifecycle import attach_event_handlers, build_bot, load_extensions, startup

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")
if not TOKEN:
    logger.error("CRITICAL: TOKEN is not set")
    sys.exit(1)


async def main() -> None:
    """Build and run the bot."""
    bot = build_bot()
    attach_event_handlers(bot, send_error_to_discord)
    set_bot_instance(bot)

    async with bot:
        try:
            await startup()
            await load_extensions(bot)
        except Exception:
            logger.exception("Startup failed")
            sys.exit(1)
        assert TOKEN is not None
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
