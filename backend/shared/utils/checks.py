"""utils/checks.py"""

import functools
import logging
from collections.abc import Callable
from typing import Any

import discord
from discord import app_commands

from shared.core.bot_context import get_current_bot_name
from shared.core.bots import get_spec
from shared.core.database import AsyncSessionLocal
from shared.core.enums import FeatureFlagNames
from shared.core.error_reporter import send_error_to_discord
from shared.repositories.feature_flags_repository import FeatureFlagsRepository

logger = logging.getLogger(__name__)


def is_admin():
    """
    A decorator that checks if the user has administrator permissions.

    Returns:
        Callable: The decorated command.
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        # Ensure this is used in a guild (not a DM)
        if not interaction.guild or not interaction.user:
            return False

        member = interaction.user

        # Check for Administrator permission
        if isinstance(member, discord.Member):
            return member.guild_permissions.administrator
        return False

    return app_commands.check(predicate)


def feature_flag_enabled(feature: FeatureFlagNames, enable_logs: bool = True):
    """
    A decorator that checks if a feature flag is enabled before executing a command or job.

    If the feature is disabled, it sends an ephemeral message to the user for commands,
    or simply logs a message and returns for jobs.

    Args:
        feature (str): The name of the feature flag to check.
        enable_logs (bool, optional): Whether to log when a feature is disabled. Defaults to True.

    Returns:
        Callable: The decorated function.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            interaction: discord.Interaction | None = None
            # Find the interaction object from the arguments, if it exists.
            # This allows the decorator to work on both regular functions (jobs)
            # and discord.py command methods.
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    interaction = arg
                    break
            if not interaction:
                for value in kwargs.values():
                    if isinstance(value, discord.Interaction):
                        interaction = value
                        break

            feature_is_enabled = False  # Default to false
            try:
                if feature in FeatureFlagsRepository._cache:
                    feature_is_enabled = FeatureFlagsRepository._cache[feature]
                else:
                    async with AsyncSessionLocal() as session:
                        feature_flag = await FeatureFlagsRepository.get_feature_flag_status(
                            session, feature
                        )
                    if feature_flag is not None:
                        feature_is_enabled = feature_flag
            except Exception:
                if enable_logs:
                    logger.exception("Error fetching feature flag '%s'", feature)
                if interaction:
                    await interaction.response.send_message(
                        "Sorry, there was an error checking the command's availability.",
                        ephemeral=True,
                    )
                else:
                    await send_error_to_discord(
                        f"**Error** checking feature flag `{feature}` in scheduled job"
                    )
                return

            if not feature_is_enabled:
                if interaction:
                    if enable_logs:
                        logger.info(
                            "Feature '%s' is disabled. Blocking command for %s.",
                            feature,
                            interaction.user,
                        )
                    await interaction.response.send_message(
                        f"This command is currently disabled by feature flag '{feature}'.",
                        ephemeral=True,
                    )
                else:
                    if enable_logs:
                        logger.info("Feature '%s' is disabled. Blocking job.", feature)
                return

            # If the flag is enabled, run the original command function.
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def bot_enabled(func: Callable) -> Callable:
    """
    A decorator that gates a command or job behind the current bot's kill switch.

    Resolves the running bot from `current_bot_var` and delegates to
    `feature_flag_enabled` with that bot's `kill_switch_flag`. Cogs never name
    their bot's flag directly, so moving a cog between bots (or into
    `shared/cogs`) needs no edits.

    If no bot is set (e.g. a unit test without the context var configured),
    this fails closed: it logs a warning and, if an `Interaction` is present
    in the arguments, sends an ephemeral "unavailable" message.

    Args:
        func: The command or job function to wrap.

    Returns:
        Callable: The decorated function.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        bot_name = get_current_bot_name()
        if bot_name is None:
            logger.warning(
                "bot_enabled: no current bot set; blocking '%s'.", getattr(func, "__name__", func)
            )
            interaction: discord.Interaction | None = None
            for arg in args:
                if isinstance(arg, discord.Interaction):
                    interaction = arg
                    break
            if interaction is None:
                for value in kwargs.values():
                    if isinstance(value, discord.Interaction):
                        interaction = value
                        break
            if interaction is not None:
                await interaction.response.send_message(
                    "This command is currently unavailable.",
                    ephemeral=True,
                )
            return None

        flag = get_spec(bot_name).kill_switch_flag
        return await feature_flag_enabled(flag)(func)(*args, **kwargs)

    return wrapper
