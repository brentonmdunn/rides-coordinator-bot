import logging
import os
import sys
import traceback

import discord

from bot.core.bot_instance import get_bot
from bot.core.enums import FeatureFlagNames

logger = logging.getLogger(__name__)


def _get_config() -> tuple[str, int | None]:
    app_env = os.getenv("APP_ENV", "local")
    raw = os.getenv("ERROR_CHANNEL_ID")
    channel_id = int(raw) if raw else None
    return app_env, channel_id


def _is_send_errors_enabled() -> bool:
    from bot.repositories.feature_flags_repository import FeatureFlagsRepository

    flag_value = FeatureFlagNames.SEND_ERRORS_TO_DISCORD.value
    return FeatureFlagsRepository._cache.get(flag_value, False)


async def send_error_to_discord(
    error_msg: str, error: Exception | None = None, tb_text: str | None = None
) -> None:
    """
    Send an error message and optional traceback to the configured Discord error channel.
    If `error` is provided, it extracts the traceback directly from the Exception object.
    If neither `error` nor `tb_text` is provided, it attempts to extract the traceback
    from sys.exc_info().
    """
    app_env, error_channel_id = _get_config()
    if app_env == "local" or error_channel_id is None:
        return

    if not _is_send_errors_enabled():
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
            exc_info = sys.exc_info()
            if exc_info[0] is not None:
                tb_lines = traceback.format_exception(*exc_info)
                tb_text = "".join(tb_lines)

    try:
        channel = bot.get_channel(error_channel_id)
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
            logger.warning(f"Error channel {error_channel_id} not found or not a text channel")
    except Exception:
        logger.exception(f"Failed to send error to Discord channel {error_channel_id}")
