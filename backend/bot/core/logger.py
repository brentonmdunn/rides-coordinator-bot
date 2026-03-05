"""Logger configuration.

This module sets up the logging configuration for the application, including
console handlers, file handlers with rotation, formatters, and log levels for
external libraries.
"""

import contextvars
import functools
import logging
import os
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import discord
from dotenv import load_dotenv

load_dotenv()

# Determine log file path
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"


user_email_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_email", default="-")
txn_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("txn_id", default="-")


def generate_txn_id() -> str:
    """Generate a short unique transaction ID (8 hex chars)."""
    return uuid.uuid4().hex[:8]


class UserEmailFilter(logging.Filter):
    """Injects the current user's email into the log record."""

    def filter(self, record):
        record.user_email = user_email_var.get()
        return True


class TransactionIdFilter(logging.Filter):
    """Injects the current transaction ID into the log record."""

    def filter(self, record):
        record.txn_id = txn_id_var.get()
        return True


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
console_handler.addFilter(UserEmailFilter())
console_handler.addFilter(TransactionIdFilter())

formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s [txn:%(txn_id)s] [%(filename)s:%(lineno)d %(name)s] [%(user_email)s] %(message)s"  # noqa: E501
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

# ------------------------------
# File handler with rotation
# ------------------------------
# Rotate logs when they reach 10MB, keep 5 backup files
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,
    encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
file_handler.addFilter(UserEmailFilter())
file_handler.addFilter(TransactionIdFilter())
logger.addHandler(file_handler)


# ------------------------------
# Decorators
# ------------------------------
def log_cmd(func):
    """A decorator that logs Discord slash commands, including their arguments.

    Args:
        func: The command function to wrap.

    Returns:
        The wrapped function.
    """

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

        txn_token = txn_id_var.set(generate_txn_id())
        email_token = user_email_var.set(str(user))
        try:
            logger.info(log)
            return await func(self, interaction, *args, **kwargs)
        finally:
            user_email_var.reset(email_token)
            txn_id_var.reset(txn_token)

    return wrapper


def log_job(func):
    """A decorator that assigns a transaction ID to a scheduled job execution.

    Args:
        func: The job function to wrap.

    Returns:
        The wrapped function.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        txn_token = txn_id_var.set(generate_txn_id())
        try:
            return await func(*args, **kwargs)
        finally:
            txn_id_var.reset(txn_token)

    return wrapper
