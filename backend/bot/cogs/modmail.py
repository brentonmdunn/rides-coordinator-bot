"""Cog for the modmail feature: relays DMs between users and staff channels."""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.enums import FeatureFlagNames
from bot.core.error_reporter import send_error_to_discord
from bot.core.logger import log_cmd
from bot.services.modmail_service import (
    ModmailConfigError,
    ModmailDMForbiddenError,
    ModmailService,
)
from bot.utils.checks import feature_flag_enabled

logger = logging.getLogger(__name__)


class Modmail(commands.Cog):
    """
    Cog for the modmail feature.

    Relays DMs between users and the bot through per-user staff channels:
    - Inbound user DMs are mirrored into a dedicated channel per user.
    - Staff messages in that channel are DM'd back to the user.
    - Staff can initiate a DM with `/dm`.
    - `/close-modmail` archives the current modmail channel.
    """

    def __init__(self, bot: commands.Bot, modmail_service: ModmailService):
        """
        Initialize the Modmail cog.

        Args:
            bot: The Discord bot instance.
            modmail_service: The service handling modmail business logic.
        """
        self.bot = bot
        self.service = modmail_service

    # ------------------------------------------------------------------
    # Event listeners
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        Relay DMs between users and modmail channels.

        Args:
            message: The incoming Discord message.
        """
        if message.author.bot:
            return

        if not await _feature_enabled():
            return

        try:
            if message.guild is None:
                # Inbound DM → mirror into the user's modmail channel.
                await self.service.relay_dm_to_channel(message)
                return

            # Guild message → check if it's in a tracked modmail channel.
            await self.service.relay_channel_to_dm(message)
        except Exception:
            logger.exception("Modmail on_message handler failed")
            await send_error_to_discord("**Unexpected Error** in modmail relay")

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------
    @app_commands.command(
        name="dm",
        description="Send a DM to a user through modmail and log it in a staff channel.",
    )
    @app_commands.describe(
        user="The user to DM.",
        message="The message to send to the user.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_flag_enabled(FeatureFlagNames.MODMAIL)
    @log_cmd
    async def dm(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        message: str,
    ) -> None:
        """
        Start or continue a modmail conversation by DMing a user.

        Args:
            interaction: The Discord interaction.
            user: The user to DM.
            message: The message to send.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)

        if user.bot:
            await interaction.followup.send("Can't DM a bot.", ephemeral=True)
            return

        try:
            channel = await self.service.start_conversation(
                user=user,
                content=message,
                initiator=interaction.user,
                guild=interaction.guild,
            )
        except ModmailConfigError as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)
            return
        except ModmailDMForbiddenError:
            await interaction.followup.send(
                f"❌ Could not DM {user.mention}: they have DMs closed or do "
                "not share a server with the bot.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"✉️ DM sent to {user.mention}. Continue the conversation in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="close-modmail",
        description="Close and delete the current modmail channel.",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    @feature_flag_enabled(FeatureFlagNames.MODMAIL)
    @log_cmd
    async def close_modmail(self, interaction: discord.Interaction) -> None:
        """
        Close the modmail channel the command is invoked in.

        Args:
            interaction: The Discord interaction.
        """
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "This command must be used inside a modmail channel.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        closed = await self.service.close_channel(channel)
        if not closed:
            await interaction.followup.send(
                "This doesn't appear to be a tracked modmail channel.",
                ephemeral=True,
            )


async def _feature_enabled() -> bool:
    """Check the modmail feature flag without going through a command interaction."""
    from bot.core.database import AsyncSessionLocal
    from bot.repositories.feature_flags_repository import FeatureFlagsRepository

    cached = FeatureFlagsRepository._cache.get(FeatureFlagNames.MODMAIL.value)
    if cached is not None:
        return cached
    async with AsyncSessionLocal() as session:
        result = await FeatureFlagsRepository.get_feature_flag_status(
            session,
            FeatureFlagNames.MODMAIL,
        )
    return bool(result)


async def setup(bot: commands.Bot) -> None:
    """
    Add the Modmail cog to the bot.

    Args:
        bot: The Discord bot instance to add the cog to.
    """
    service = ModmailService(bot)
    await bot.add_cog(Modmail(bot, service))
