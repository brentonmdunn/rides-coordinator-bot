"""Main entry point for the bots."""

import asyncio
import logging
import sys

from dotenv import load_dotenv

from shared.core.bots import resolve_enabled_bots
from shared.core.lifecycle import run_bot, startup

logger = logging.getLogger(__name__)


async def main() -> None:
    """Resolve enabled bots, run startup once, then run every enabled bot."""
    load_dotenv()
    enabled_bots = resolve_enabled_bots()

    try:
        await startup()
    except Exception:
        logger.exception("Startup failed")
        sys.exit(1)

    await asyncio.gather(*(run_bot(enabled.spec, enabled.token) for enabled in enabled_bots))


if __name__ == "__main__":
    asyncio.run(main())
