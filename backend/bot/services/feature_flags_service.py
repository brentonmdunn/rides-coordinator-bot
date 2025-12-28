"""Service layer for feature flag logic and validation."""

import discord

from bot.core.enums import FeatureFlagNames
from bot.repositories.feature_flags_repository import FeatureFlagsRepository


class FeatureFlagsService:
    """Handles feature flag business logic between the Cog and Repository."""

    def __init__(self, repository: FeatureFlagsRepository):
        """Initialize the FeatureFlagsService."""

        self.repository = repository

    async def validate_feature_name(self, feature_name: str) -> FeatureFlagNames | None:
        """Validate and convert a feature name to an enum member.

        Args:
            feature_name (str): The name of the feature flag to validate.

        Returns:
            FeatureFlagNames | None: The corresponding FeatureFlagNames enum member, or None
                                     if invalid.
        """
        try:
            return FeatureFlagNames(feature_name)
        except ValueError:
            return None

    async def modify_feature_flag(self, feature_name: str, enabled: bool) -> tuple[bool, str]:
        """Modify a feature flag state and return a message tuple (success, message).

        Args:
            feature_name (str): The name of the feature flag to modify.
            enabled (bool): Whether to enable or disable the flag.

        Returns:
            tuple[bool, str]: A tuple containing a boolean indicating success and a status message.
        """
        flag = await FeatureFlagsRepository.get_feature_flag(feature_name)

        if not flag:
            return False, f"❓ Flag `{feature_name}` not found. It should be seeded automatically."

        if flag.enabled == enabled:
            state = "enabled" if enabled else "disabled"
            return False, f"ℹ️ Feature flag `{feature_name}` is already **{state}**."  # noqa

        await FeatureFlagsRepository.update_feature_flag(feature_name, enabled)
        new_state = "enabled" if enabled else "disabled"
        return True, f"✅ Feature flag `{feature_name}` is now **{new_state}**."

    async def list_feature_flags_embed(self) -> discord.Embed:
        """Return a Discord embed listing all feature flags and their current states.

        Returns:
            discord.Embed: A Discord Embed object containing the list of feature flags.
        """
        all_flags = await FeatureFlagsRepository.get_all_feature_flags()

        embed = discord.Embed(
            title="⚙️ Feature Flag Status",
            description="Current state of all defined feature flags.",
            color=discord.Color.blue(),
        )

        for flag in all_flags:
            status_icon = "✅" if flag.enabled else "❌"
            status_text = "Enabled" if flag.enabled else "Disabled"
            embed.add_field(name=flag.feature, value=f"{status_icon} {status_text}", inline=False)

        return embed
