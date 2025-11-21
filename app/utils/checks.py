"""utils/checks.py"""
import functools
from collections.abc import Callable
from typing import Any

import discord
from discord import app_commands

from app.core.logger import logger
from app.repositories.feature_flags_repository import FeatureFlagsRepository


def is_admin():
    """A decorator that checks if the user has administrator permissions.

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


def feature_flag_enabled(feature: str, enable_logs: bool = True):
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
                feature_flag = await FeatureFlagsRepository.get_feature_flag_status(feature)
                if feature_flag is not None:
                    feature_is_enabled = feature_flag
            except Exception as e:
                if enable_logs:
                    logger.error("Error fetching feature flag '%s': %s", feature, e)
                if interaction:
                    await interaction.response.send_message(
                        "Sorry, there was an error checking the command's availability.",
                        ephemeral=True,
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
