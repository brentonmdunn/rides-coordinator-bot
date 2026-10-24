"""Reconcile ride sources on ready/resume and every five minutes."""

import asyncio
import logging

from discord.ext import commands, tasks

from ridebot.services.ride_event_sync_service import RideEventSyncService

logger = logging.getLogger(__name__)


class RideEventSync(commands.Cog):
    """Own one supervised, serialized reconciliation loop per bot process."""

    def __init__(self, bot):
        """Initialize adapter and lock; the loop waits for the bot to become ready."""
        self.bot = bot
        self.service = RideEventSyncService(bot)
        self.lock = asyncio.Lock()
        self.needs_discovery = True

    async def cog_load(self):
        """Support hot reload; initial extension loading happens before client initialization."""
        if self.bot.is_ready():
            self.reconcile.start()

    def cog_unload(self):
        """Cancel in-flight work when the cog/process shuts down."""
        self.reconcile.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Request discovery and immediate reconciliation after a fresh gateway session."""
        self.needs_discovery = True
        if not self.reconcile.is_running():
            self.reconcile.start()
        await self.run_sync()

    @commands.Cog.listener()
    async def on_resumed(self):
        """Repair missed changes after a resumed gateway session."""
        self.needs_discovery = True
        if not self.reconcile.is_running():
            self.reconcile.start()
        await self.run_sync()

    async def run_sync(self):
        """Coalesce overlapping ready/resume/timer triggers."""
        if self.lock.locked() or not self.bot.is_ready():
            return
        async with self.lock:
            try:
                discovered = await self.service.run(discover=self.needs_discovery)
                self.needs_discovery = not discovered
            except Exception:
                logger.exception("Ride reconciliation failed; the next interval will retry")

    @tasks.loop(minutes=5)
    async def reconcile(self):
        """Refresh recent source snapshots on a bounded schedule."""
        await self.run_sync()

    @reconcile.before_loop
    async def before_reconcile(self):
        """Prevent REST/discovery calls before authentication and guild cache readiness."""
        await self.bot.wait_until_ready()


async def setup(bot):
    """Load the per-RideBot reconciliation owner."""
    await bot.add_cog(RideEventSync(bot))
