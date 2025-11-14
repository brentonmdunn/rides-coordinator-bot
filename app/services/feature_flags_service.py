"""Service layer for feature flag logic and validation."""

import discord

from app.core.enums import FeatureFlagNames
from app.repositories.feature_flags_repository import FeatureFlagsRepository


class FeatureFlagsService:
    """Handles feature flag business logic between the Cog and Repository."""

    @staticmethod
    async def validate_feature_name(feature_name: str) -> FeatureFlagNames | None:
        """Validate and convert a feature name to an enum member."""
        try:
            return FeatureFlagNames(feature_name)
        except ValueError:
            return None

    @staticmethod
    async def modify_feature_flag(feature_name: str, enabled: bool) -> tuple[bool, str]:
        """Modify a feature flag state and return a message tuple (success, message)."""
        flag = await FeatureFlagsRepository.get_feature_flag(feature_name)

        if not flag:
            return False, f"❓ Flag `{feature_name}` not found. It should be seeded automatically."

        if flag.enabled == enabled:
            state = "enabled" if enabled else "disabled"
            return False, f"ℹ️ Feature flag `{feature_name}` is already **{state}**."  # noqa

        await FeatureFlagsRepository.update_feature_flag(feature_name, enabled)
        new_state = "enabled" if enabled else "disabled"
        return True, f"✅ Feature flag `{feature_name}` is now **{new_state}**."

    @staticmethod
    async def list_feature_flags_embed() -> discord.Embed:
        """Return a Discord embed listing all feature flags and their current states."""
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
