import functools
import logging
import os
from typing import Any

import discord
from dotenv import load_dotenv

load_dotenv()


LOG_PATH = os.getenv("LOG_PATH")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Print stream handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# File handler
# file_handler = logging.FileHandler(LOG_PATH)
# file_handler.setLevel(logging.DEBUG)


formatter = logging.Formatter(
    "%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s",
)

console_handler.setFormatter(formatter)
# file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
# logger.addHandler(file_handler)


def log_cmd(func):
    """
    A decorator that logs Discord slash commands, preserving the function signature.
    """

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
        logger.info(
            f"command={interaction.data['name']} used by user={interaction.user} in channel={interaction.channel}."  # noqa
        )
        return await func(self, interaction, *args, **kwargs)

    return wrapper
