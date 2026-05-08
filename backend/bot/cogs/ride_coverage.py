"""Cog for ride coverage logic."""

import logging

import discord
from discord.ext import commands

from bot.core.database import AsyncSessionLocal
from bot.core.enums import ChannelIds
from bot.core.error_reporter import send_error_to_discord
from bot.repositories.ride_coverage_repository import RideCoverageRepository
from bot.services.ride_coverage_service import RideCoverageService

logger = logging.getLogger(__name__)


class RideCoverage(commands.Cog):
    """Cog for handling ride coverage tracking."""

    def __init__(self, bot: commands.Bot):
        """Initialize the RideCoverage cog."""
        self.bot = bot
        self._service = RideCoverageService(bot)
        self._synced_on_startup = False
        logger.info("RideCoverage cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Sync missed messages when bot is ready."""
        if self._synced_on_startup:
            return  # Only sync once per session

        self._synced_on_startup = True
        logger.info("RideCoverage: Bot is ready, starting startup sync...")
        await self._service.sync_ride_coverage()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener for new messages to detect ride coverage."""
        if message.author.bot:
            return

        logger.debug(f"on_message: Received message {message.id} from {message.author}")

        if not RideCoverageService.is_grouping_message(message):
            return

        logger.debug(f"on_message: Message {message.id} is a grouping message")

        passenger_usernames = RideCoverageService.extract_passengers(message)

        if passenger_usernames:
            logger.info(
                f"on_message: Detected ride coverage for: {passenger_usernames} "
                f"(message_id={message.id})"
            )

            try:
                async with AsyncSessionLocal() as session:
                    await RideCoverageRepository.add_coverage_entries(
                        session, passenger_usernames, str(message.id)
                    )
                logger.info(
                    f"on_message: Successfully added {len(passenger_usernames)} coverage entries"
                )
            except Exception:
                logger.exception("on_message: Failed to record ride coverage")
                await send_error_to_discord(
                    "**Unexpected Error** in `on_message` ride coverage recording"
                )
        else:
            logger.debug(f"on_message: No passengers found in message {message.id}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Listener for message edit events to sync ride coverage."""
        if after.author.bot:
            return

        logger.debug(f"on_message_edit: Message {after.id} edited by {after.author}")

        if not RideCoverageService.is_grouping_message(after):
            logger.debug(f"on_message_edit: Message {after.id} is not a grouping message, skipping")
            return

        logger.debug(f"on_message_edit: Message {after.id} is a grouping message, processing edit")

        before_passengers = set(RideCoverageService.extract_passengers(before))
        after_passengers = set(RideCoverageService.extract_passengers(after))

        logger.debug(f"on_message_edit: Before passengers: {before_passengers}")
        logger.debug(f"on_message_edit: After passengers: {after_passengers}")

        added = after_passengers - before_passengers
        removed = before_passengers - after_passengers

        logger.debug(f"on_message_edit: Added: {added}, Removed: {removed}")

        if added:
            logger.info(
                f"on_message_edit: Ride coverage added via edit: {list(added)} "
                f"(message_id={after.id})"
            )

            try:
                async with AsyncSessionLocal() as session:
                    await RideCoverageRepository.add_coverage_entries(
                        session, list(added), str(after.id)
                    )
                logger.info(f"on_message_edit: Successfully added {len(added)} coverage entries")
            except Exception:
                logger.exception("on_message_edit: Failed to add ride coverage on edit")
                await send_error_to_discord(
                    "**Unexpected Error** in `on_message_edit` adding ride coverage"
                )

        if removed:
            logger.info(
                f"on_message_edit: Ride coverage removed via edit: {list(removed)} "
                f"(message_id={after.id})"
            )

            try:
                async with AsyncSessionLocal() as session:
                    await RideCoverageRepository.delete_coverage_entries(
                        session, list(removed), str(after.id)
                    )
                logger.info(
                    f"on_message_edit: Successfully removed {len(removed)} coverage entries"
                )
            except Exception:
                logger.exception("on_message_edit: Failed to remove ride coverage on edit")
                await send_error_to_discord(
                    "**Unexpected Error** in `on_message_edit` removing ride coverage"
                )

        if not added and not removed:
            logger.debug(f"on_message_edit: No passenger changes detected for message {after.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Listener for message delete events to remove ride coverage."""
        logger.debug(f"on_message_delete: Message {message.id} deleted by {message.author}")

        if message.channel.id not in [
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
            ChannelIds.BOT_STUFF__BOT_SPAM_2,  # For testing
        ]:
            return

        try:
            async with AsyncSessionLocal() as session:
                deleted_count = await RideCoverageRepository.delete_all_entries_by_message(
                    session, str(message.id)
                )
            if deleted_count > 0:
                logger.info(
                    f"on_message_delete: Removed {deleted_count} coverage entries "
                    f"for deleted message {message.id}"
                )

            else:
                logger.debug(
                    f"on_message_delete: No coverage entries found for message {message.id}"
                )
        except Exception:
            logger.exception("on_message_delete: Failed to remove coverage entries")
            await send_error_to_discord(
                "**Unexpected Error** in `on_message_delete` removing coverage entries"
            )


async def setup(bot: commands.Bot):
    """Sets up the RideCoverage cog."""
    await bot.add_cog(RideCoverage(bot))
