# utils/checks.py
import functools
from typing import Any, Callable

import discord
from discord import app_commands
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.models import FeatureFlags


def is_admin():
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


def feature_flag_enabled(feature: str):
    """
    A decorator that checks if a feature flag is enabled before executing a command.
    If the feature is disabled, it sends an ephemeral message to the user.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        # The signature must include `self` as the first argument because it's
        # decorating a class method.
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs) -> Any:
            feature_is_enabled = False  # Default to false
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(FeatureFlags).where(FeatureFlags.feature == feature)
                    )
                    feature_flag = result.scalars().first()
                    if feature_flag:
                        feature_is_enabled = feature_flag.enabled
            except Exception as e:
                print(f"Error fetching feature flag '{feature}': {e}")
                await interaction.response.send_message(
                    "Sorry, there was an error checking the command's availability.", ephemeral=True
                )
                return

            if not feature_is_enabled:
                print(f"Feature '{feature}' is disabled. Blocking command for {interaction.user}.")
                await interaction.response.send_message(
                    f"This command is currently disabled by feature flag '{feature}'.",
                    ephemeral=True,
                )
                return

            # If the flag is enabled, run the original command function.
            return await func(self, interaction, *args, **kwargs)

        return wrapper

    return decorator


def feature_flag_enabled_jobs(feature: str):
    """
    A decorator that checks if a feature flag is enabled before executing a command.
    If the feature is disabled, it sends an ephemeral message to the user.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            feature_is_enabled = False  # Default to false
            try:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(FeatureFlags).where(FeatureFlags.feature == feature)
                    )
                    feature_flag = result.scalars().first()
                    if feature_flag:
                        feature_is_enabled = feature_flag.enabled
            except Exception as e:
                print(f"Error fetching feature flag '{feature}': {e}")
                return

            if not feature_is_enabled:
                print(f"Feature '{feature}' is disabled. Blocking command for job.")
                return

            # If the flag is enabled, run the original command function.
            return await func(*args, **kwargs)

        return wrapper

    return decorator
