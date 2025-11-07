import functools
import logging
import os
from typing import Any

import discord
from dotenv import load_dotenv

load_dotenv()

LOG_PATH = os.getenv("LOG_PATH")

# ------------------------------
# Root logger setup (your code)
# ------------------------------
logger = logging.getLogger()
# Set level based on the environment
log_level = logging.DEBUG if os.getenv("APP_ENV", "local") == "local" else logging.INFO
logger.setLevel(log_level)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Allow DEBUG output for your code

formatter = logging.Formatter(
    "%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d %(name)s] %(message)s"
)

console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# ------------------------------
# Reduce verbosity for 3rd-party libs
# ------------------------------
# List of commonly noisy external libraries
noisy_loggers = [
    "discord",  # discord.py
    "asyncio",  # asyncio warnings
    "websockets",  # if using websockets
    "sqlalchemy",  # ORM logs
    "tzlocal",  # ORM logs
    "aiosqlite",  # ORM logs
    "apscheduler.scheduler",  # ORM logs
]

for lib in noisy_loggers:
    logging.getLogger(lib).setLevel(logging.INFO)

logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm.mapper.Mapper").setLevel(logging.WARNING)

# Optional file handler
# file_handler = logging.FileHandler(LOG_PATH)
# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(formatter)
# logger.addHandler(file_handler)


# ------------------------------
# Decorator
# ------------------------------
def log_cmd(func):
    """A decorator that logs Discord slash commands, including their arguments."""

    @functools.wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args: Any, **kwargs: Any) -> Any:
        command_name = interaction.data.get("name", "unknown_command")
        user = interaction.user
        channel = interaction.channel

        # Extract and format arguments from the interaction data
        options = interaction.data.get("options", [])
        arg_list = []
        for option in options:
            arg_list.append(f"{option['name']}:{option['value']}")

        # Create a string of comma-separated arguments
        args_str = ", ".join(arg_list)

        log = f"command=/{command_name} used by user={user} in channel={channel}."
        if args_str:
            log += f" arguments=[{args_str}]"
        logger.info(log)

        return await func(self, interaction, *args, **kwargs)

    return wrapper
