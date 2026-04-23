"""Main entry point for the bot."""

import asyncio
import logging
import os

from dotenv import load_dotenv

from bot.core.bot_instance import set_bot_instance
from bot.core.error_reporter import send_error_to_discord
from bot.core.lifecycle import attach_event_handlers, build_bot, load_extensions, startup

logger = logging.getLogger(__name__)

load_dotenv()
TOKEN: str | None = os.getenv("TOKEN")


async def main() -> None:
    """Build and run the bot."""
    bot = build_bot()
    attach_event_handlers(bot, send_error_to_discord)
    set_bot_instance(bot)

    async with bot:
        await startup()
        await load_extensions(bot)
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
