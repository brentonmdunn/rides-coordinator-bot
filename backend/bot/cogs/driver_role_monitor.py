"""Cog that logs Driver and Ride Coordinator role changes made outside the dashboard."""

import logging

import discord
from discord.ext import commands

from bot.core.enums import RoleIds

logger = logging.getLogger(__name__)

_MONITORED_ROLES: dict[int, str] = {
    int(RoleIds.DRIVER): "Driver",
    int(RoleIds.RIDE_COORDINATOR): "Ride Coordinator",
}


class DriverRoleMonitor(commands.Cog):
    """Monitors Driver and Ride Coordinator role additions and removals not originating from the dashboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log managed role changes that originate outside the dashboard."""
        before_ids = {r.id for r in before.roles}
        after_ids = {r.id for r in after.roles}

        for role_id, role_name in _MONITORED_ROLES.items():
            if role_id in after_ids and role_id not in before_ids:
                logger.info(
                    "%s role added to @%s (%s) outside the dashboard",
                    role_name,
                    after.name,
                    after.id,
                )
            elif role_id in before_ids and role_id not in after_ids:
                logger.info(
                    "%s role removed from @%s (%s) outside the dashboard",
                    role_name,
                    after.name,
                    after.id,
                )


async def setup(bot: commands.Bot):
    """Sets up the DriverRoleMonitor cog."""
    await bot.add_cog(DriverRoleMonitor(bot))
