import logging

from discord.ext.commands import Bot

logger = logging.getLogger(__name__)

_bot_instance: Bot | None = None


def get_bot() -> Bot | None:
    """Return the bot instance if it is running and ready, otherwise None."""
    return _bot_instance if _bot_instance and _bot_instance.is_ready() else None


def set_bot_instance(bot: Bot | None) -> None:
    """Set the global bot instance (called by the lifecycle manager)."""
    global _bot_instance
    _bot_instance = bot
