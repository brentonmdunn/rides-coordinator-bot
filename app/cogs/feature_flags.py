"""Discord Cog providing feature flag management commands."""

import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.repositories.feature_flags_repository import FeatureFlagsRepository
from app.services.feature_flags_service import FeatureFlagsService
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed


async def feature_name_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Autocompletes feature flag names based on current user input.

    Args:
        interaction: The Discord interaction.
        current: The current input string.

    Returns:
        A list of matching feature flag choices.
    """
    flags = [flag.value for flag in FeatureFlagNames]
    return [
        app_commands.Choice(name=flag, value=flag)
        for flag in flags
        if current.lower() in flag.lower()
    ]


class FeatureFlagsCog(commands.Cog):
    """Cog that exposes commands for listing and modifying feature flags."""

    def __init__(self, bot: commands.Bot, feature_flags_service: FeatureFlagsService):
        self.bot = bot
        self.feature_flags_service = feature_flags_service

    @app_commands.command(name="feature-flag", description="Enable or disable a feature flag.")
    @app_commands.autocomplete(feature_name=feature_name_autocomplete)
    @log_cmd
    async def modify_feature_flag(
        self, interaction: discord.Interaction, feature_name: str, enabled: bool
    ) -> None:
        """Slash command for enabling/disabling a feature flag.

        Args:
            interaction: The Discord interaction.
            feature_name: The name of the feature flag.
            enabled: Whether to enable or disable the flag.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        # Validate feature flag name
        feature_enum = await self.feature_flags_service.validate_feature_name(feature_name)
        if not feature_enum:
            await interaction.response.send_message(
                f"❌ `{feature_name}` is not a valid feature flag.", ephemeral=True
            )
            return

        success, message = await self.feature_flags_service.modify_feature_flag(
            feature_name, enabled
        )
        await interaction.response.send_message(message, ephemeral=not success)

    @app_commands.command(
        name="list-feature-flags",
        description="Lists all feature flags and their current status.",
    )
    @log_cmd
    async def list_feature_flags(self, interaction: discord.Interaction) -> None:
        """Slash command to list all feature flags in an embed.

        Args:
            interaction: The Discord interaction.
        """
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        embed = await self.feature_flags_service.list_feature_flags_embed()
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the FeatureFlagsCog to the Discord bot.

    Args:
        bot: The Discord bot instance.
    """
    repo = FeatureFlagsRepository()
    service = FeatureFlagsService(repository=repo)
    await bot.add_cog(FeatureFlagsCog(bot, feature_flags_service=service))
