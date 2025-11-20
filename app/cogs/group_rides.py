import discord
from discord import app_commands
from discord.ext import commands

from app.core.enums import FeatureFlagNames
from app.core.logger import log_cmd
from app.services.group_rides_service import GroupRidesService
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled


class GroupRides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.service = GroupRidesService(bot)

    @app_commands.command(
        name="group-rides-friday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_friday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.group_rides(
            interaction, driver_capacity, day="friday", legacy_prompt=legacy_prompt
        )

    @app_commands.command(
        name="group-rides-sunday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_sunday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.group_rides(
            interaction, driver_capacity, day="sunday", legacy_prompt=legacy_prompt
        )

    @app_commands.command(
        name="group-rides-by-message-id",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_message_id(
        self,
        interaction: discord.Interaction,
        message_id: str,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self.service.group_rides(
            interaction, driver_capacity, message_id=message_id, legacy_prompt=legacy_prompt
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupRides(bot))
