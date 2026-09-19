"""Cog for granting, revoking, and listing temporary Driver role grants."""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from ridebot.services.temp_driver_service import TempDriverResult, TempDriverService
from shared.core.enums import ChannelIds
from shared.core.error_reporter import send_error_to_discord
from shared.core.logger import log_cmd
from shared.utils.channels import resolve_channel_id
from shared.utils.checks import bot_enabled, is_ride_coordinator
from shared.utils.constants import LA_TZ

logger = logging.getLogger(__name__)


def _format_la_when(expires_at: datetime) -> str:
    """Format an aware UTC datetime as e.g. 'Sat, Oct 5, 11:59 PM' in LA time."""
    la = expires_at.astimezone(LA_TZ)
    # %I zero-pads the hour (e.g. "09:00 PM"); strip that leading zero.
    return la.strftime("%a, %b %-d, %I:%M %p").replace(", 0", ", ")


class TempDrivers(commands.Cog):
    """Slash commands for managing temporary Driver role grants."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _respond(
        self, interaction: discord.Interaction, result: TempDriverResult, in_channel: bool
    ) -> None:
        """Route the response: announce in-channel, or confirm ephemerally elsewhere."""
        if in_channel:
            await interaction.response.send_message(
                result.announcement, allowed_mentions=discord.AllowedMentions.none()
            )
        else:
            await interaction.response.send_message(
                f"✅ Done — announced in <#{resolve_channel_id(ChannelIds.SERVING__RIDE_COORDINATORS)}>.",
                ephemeral=True,
            )

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
        # Compares the invoking channel against the destination channel for the
        # announcement, not against an "incoming event" channel — intentional.
        in_channel = interaction.channel_id == resolve_channel_id(
            ChannelIds.SERVING__RIDE_COORDINATORS
        )
        try:
            result = await TempDriverService(self.bot).grant(
                user,
                duration,
                interaction.user.display_name,
                announce=not in_channel,
            )
        except (ValueError, PermissionError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        except Exception:
            logger.exception("Failed to add temporary driver")
            await send_error_to_discord("**Error** adding temporary driver")
            await interaction.response.send_message(
                "Something went wrong adding that temporary driver.", ephemeral=True
            )
            return

        await self._respond(interaction, result, in_channel)

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
        # Compares the invoking channel against the destination channel for the
        # announcement, not against an "incoming event" channel — intentional.
        in_channel = interaction.channel_id == resolve_channel_id(
            ChannelIds.SERVING__RIDE_COORDINATORS
        )
        try:
            result = await TempDriverService(self.bot).revoke(
                str(user.id),
                interaction.user.display_name,
                announce=not in_channel,
            )
        except (ValueError, PermissionError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        except Exception:
            logger.exception("Failed to remove temporary driver")
            await send_error_to_discord("**Error** removing temporary driver")
            await interaction.response.send_message(
                "Something went wrong removing that temporary driver.", ephemeral=True
            )
            return

        await self._respond(interaction, result, in_channel)

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
                f"**{grant.display_name}** — {_format_la_when(grant.expires_at)} "
                f"(<t:{int(grant.expires_at.timestamp())}:R>) · by {grant.granted_by}"
                for grant in grants
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Sets up the TempDrivers cog."""
    await bot.add_cog(TempDrivers(bot))
