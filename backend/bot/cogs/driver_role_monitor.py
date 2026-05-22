"""Cog that logs Driver role changes made outside the dashboard."""

import logging

import discord
from discord.ext import commands

from bot.core.enums import RoleIds

logger = logging.getLogger(__name__)


class DriverRoleMonitor(commands.Cog):
    """Monitors Driver role additions and removals not originating from the dashboard."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log Driver role changes that originate outside the dashboard."""
        driver_role_id = int(RoleIds.DRIVER)

        before_ids = {r.id for r in before.roles}
        after_ids = {r.id for r in after.roles}

        if driver_role_id in after_ids and driver_role_id not in before_ids:
            logger.info(
                "Driver role added to @%s (%s) outside the dashboard",
                after.name,
                after.id,
            )
        elif driver_role_id in before_ids and driver_role_id not in after_ids:
            logger.info(
                "Driver role removed from @%s (%s) outside the dashboard",
                after.name,
                after.id,
            )


async def setup(bot: commands.Bot):
    """Sets up the DriverRoleMonitor cog."""
    await bot.add_cog(DriverRoleMonitor(bot))
