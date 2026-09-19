"""Cog for granting, revoking, and listing temporary Driver role grants."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ridebot.services.temp_driver_service import (
    TempDriverResult,
    TempDriverService,
    format_expiry,
)
from shared.core.enums import ChannelIds
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_cmd
from shared.utils.channels import resolve_channel_id
from shared.utils.checks import bot_enabled, is_ride_coordinator

logger = logging.getLogger(__name__)


def _when(expires_at: datetime) -> str:
    """'Sat, Oct 5, 11:59 PM (<t:…:R>)', matching the announcement format."""
    when, rel = format_expiry(expires_at)
    return f"{when} ({rel})"


class TempDrivers(commands.Cog):
    """Slash commands for managing temporary Driver role grants."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _in_coordinators_channel(interaction: discord.Interaction) -> bool:
        # Compares the invoking channel against the destination channel for the
        # announcement, not against an "incoming event" channel — intentional.
        return interaction.channel_id == resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)

    async def _run(
        self,
        interaction: discord.Interaction,
        action: Callable[[], Awaitable[TempDriverResult]],
        in_channel: bool,
        verb: str,
    ) -> None:
        """
        Defer, run the grant/revoke, then respond.

        Deferring first keeps the slow part (DB + Discord role change + announcement) from
        running past Discord's 3-second response window. In the coordinators channel the
        deferred response is public and becomes the announcement; elsewhere it's ephemeral.
        """
        await interaction.response.defer(ephemeral=not in_channel, thinking=True)
        try:
            result = await action()
        except (ValueError, PermissionError) as e:
            await self._send_error(interaction, in_channel, str(e))
            return
        except Exception:
            logger.exception("Failed %s temporary driver", verb)
            await send_error_to_discord(f"**Error** {verb} temporary driver")
            await self._send_error(
                interaction, in_channel, f"Something went wrong {verb} that temporary driver."
            )
            return

        if in_channel:
            await interaction.edit_original_response(
                content=result.announcement, allowed_mentions=discord.AllowedMentions.none()
            )
        else:
            await interaction.followup.send(
                f"✅ Done — announced in <#{resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)}>.",
                ephemeral=True,
            )

    @staticmethod
    async def _send_error(interaction: discord.Interaction, in_channel: bool, text: str) -> None:
        """Errors are always private: drop the public "thinking" placeholder first."""
        if in_channel:
            await interaction.delete_original_response()
        await interaction.followup.send(text, ephemeral=True)

    @app_commands.command(
        name="add-temp-driver",
        description="Give someone the Driver role temporarily (default 1 week).",
    )
    @app_commands.describe(
        user="The member to make a temporary driver.",
        duration="e.g. 3d, 2w, 12h, 10/5, 2026-10-05 (default 1 week, max 90 days)",
    )
    @is_ride_coordinator()
    @bot_enabled
    @log_cmd
    async def add_temp_driver(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        duration: str | None = None,
    ) -> None:
        """Grant (or extend) a temporary Driver role."""
        in_channel = self._in_coordinators_channel(interaction)
        await self._run(
            interaction,
            lambda: TempDriverService(self.bot).grant(
                user, duration, interaction.user.display_name, announce=not in_channel
            ),
            in_channel,
            "adding",
        )

    @app_commands.command(
        name="remove-temp-driver",
        description="Remove a temporary driver's Driver role early.",
    )
    @app_commands.describe(user="The temporary driver to remove.")
    @is_ride_coordinator()
    @bot_enabled
    @log_cmd
    async def remove_temp_driver(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        """Remove a temporary driver's role and grant early."""
        in_channel = self._in_coordinators_channel(interaction)
        await self._run(
            interaction,
            lambda: TempDriverService(self.bot).revoke(
                str(user.id), interaction.user.display_name, announce=not in_channel
            ),
            in_channel,
            "removing",
        )

    @app_commands.command(
        name="list-temp-drivers",
        description="List everyone with a temporary Driver role grant.",
    )
    @is_ride_coordinator()
    @bot_enabled
    @log_cmd
    async def list_temp_drivers(self, interaction: discord.Interaction) -> None:
        """Show every active temporary driver grant, soonest expiry first."""
        try:
            grants = await TempDriverService.list_grants()
        except Exception:
            logger.exception("Failed to list temporary drivers")
            await send_error_to_discord("**Error** listing temporary drivers")
            await interaction.response.send_message(
                "Something went wrong listing temporary drivers.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Temporary Drivers", color=discord.Color.blue())
        if not grants:
            embed.description = "No temporary drivers."
        else:
            embed.description = "\n".join(
                f"**{grant.display_name}** — {_when(grant.expires_at)} · by {grant.granted_by}"
                for grant in grants
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Sets up the TempDrivers cog."""
    await bot.add_cog(TempDrivers(bot))
