"""Discord Cog providing feature flag management commands."""

import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.services.feature_flags_service import FeatureFlagsService
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed


class FeatureFlagsCog(commands.Cog):
    """Cog that exposes commands for listing and modifying feature flags."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def feature_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocompletes feature flag names based on current user input."""
        flags = [flag.value for flag in FeatureFlagNames]
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in flags
            if current.lower() in flag.lower()
        ]

    @app_commands.command(name="feature-flag", description="Enable or disable a feature flag.")
    @app_commands.autocomplete(feature_name=feature_name_autocomplete)
    @log_cmd
    async def modify_feature_flag(
        self, interaction: discord.Interaction, feature_name: str, enabled: bool
    ) -> None:
        """Slash command for enabling/disabling a feature flag."""
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        # Validate feature flag name
        feature_enum = await FeatureFlagsService.validate_feature_name(feature_name)
        if not feature_enum:
            await interaction.response.send_message(
                f"❌ `{feature_name}` is not a valid feature flag.", ephemeral=True
            )
            return

        success, message = await FeatureFlagsService.modify_feature_flag(feature_name, enabled)
        await interaction.response.send_message(message, ephemeral=not success)

    @app_commands.command(
        name="list-feature-flags",
        description="Lists all feature flags and their current status.",
    )
    @log_cmd
    async def list_feature_flags(self, interaction: discord.Interaction) -> None:
        """Slash command to list all feature flags in an embed."""
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return

        embed = await FeatureFlagsService.list_feature_flags_embed()
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Add the FeatureFlagsCog to the Discord bot."""
    await bot.add_cog(FeatureFlagsCog(bot))
