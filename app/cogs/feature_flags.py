import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.core.enums import FeatureFlagNames
from app.core.models import FeatureFlags as FeatureFlagsModel
from app.utils.checks import is_admin


class FeatureFlagsCog(commands.Cog):
    """A cog for managing feature flags with slash commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def feature_name_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocompletes feature flag names from the enum."""
        flags = [flag.value for flag in FeatureFlagNames]
        return [
            app_commands.Choice(name=flag, value=flag)
            for flag in flags
            if current.lower() in flag.lower()
        ]

    @app_commands.command(
        name="feature-flag",
        description="Enable or disable a feature flag.",
    )
    @app_commands.autocomplete(feature_name=feature_name_autocomplete)
    @is_admin()
    async def modify_feature_flag(
        self, interaction: discord.Interaction, feature_name: str, enabled: bool
    ) -> None:
        """Modifies a feature flag's 'enabled' state in the database."""
        # Validate that the provided feature_name is a valid enum member
        try:
            FeatureFlagNames(feature_name)
        except ValueError:
            await interaction.response.send_message(
                f"❌ `{feature_name}` is not a valid feature flag.", ephemeral=True
            )
            return

        async with AsyncSessionLocal() as session:
            # Get the current state of the flag
            stmt_select = select(FeatureFlagsModel).where(FeatureFlagsModel.feature == feature_name)
            result = await session.execute(stmt_select)
            flag_to_update = result.scalars().first()

            if not flag_to_update:
                await interaction.response.send_message(
                    f"❓ Flag `{feature_name}` not found. It should be seeded automatically.",
                    ephemeral=True,
                )
                return

            if flag_to_update.enabled == enabled:
                state = "enabled" if enabled else "disabled"
                await interaction.response.send_message(
                    f"ℹ️ Feature flag `{feature_name}` is already **{state}**.",  # noqa: RUF001
                    ephemeral=True,
                )
                return

            stmt_update = (
                update(FeatureFlagsModel)
                .where(FeatureFlagsModel.feature == feature_name)
                .values(enabled=enabled)
            )
            await session.execute(stmt_update)
            await session.commit()

            new_state = "enabled" if enabled else "disabled"
            await interaction.response.send_message(
                f"✅ Feature flag `{feature_name}` is now **{new_state}**."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(FeatureFlagsCog(bot))
