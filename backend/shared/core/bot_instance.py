"""Process-wide registry of running bot instances."""

import logging

from discord.ext.commands import Bot

from shared.core.bots import BOT_REGISTRY
from shared.core.enums import BotName

logger = logging.getLogger(__name__)

_bots: dict[BotName, Bot] = {}


def set_bot_instance(name: BotName, bot: Bot | None) -> None:
    """Register (or with None, unregister) the running instance of a bot."""
    if bot is None:
        _bots.pop(name, None)
    else:
        _bots[name] = bot


def get_bot(name: BotName) -> Bot | None:
    """Return the named bot if it is running and ready, otherwise None."""
    bot = _bots.get(name)
    return bot if bot is not None and bot.is_ready() else None


def get_registered_bots() -> dict[BotName, Bot]:
    """Return every registered bot, ready or not."""
    return dict(_bots)


def get_ready_bots() -> dict[BotName, Bot]:
    """Return ready bots in registry order."""
    ready: dict[BotName, Bot] = {}
    for spec in BOT_REGISTRY:
        bot = _bots.get(spec.name)
        if bot is not None and bot.is_ready():
            ready[spec.name] = bot
    return ready
