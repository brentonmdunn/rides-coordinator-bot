"""Cog for ride coverage logic."""

import discord
from discord.ext import commands

from bot.core.enums import ChannelIds
from bot.core.logger import logger
from bot.repositories.ride_coverage_repository import RideCoverageRepository
from bot.utils.time_helpers import get_last_sunday


class RideCoverage(commands.Cog):
    """Cog for handling ride coverage tracking."""

    def __init__(self, bot: commands.Bot):
        """Initialize the RideCoverage cog."""

        self.bot = bot
        self.repo = RideCoverageRepository()
        self._synced_on_startup = False
        logger.info("RideCoverage cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        """Sync missed messages when bot is ready."""
        if self._synced_on_startup:
            return  # Only sync once per session

        self._synced_on_startup = True
        logger.info("RideCoverage: Bot is ready, starting startup sync...")
        await self.sync_ride_coverage()

    async def sync_ride_coverage(self) -> dict:
        """
        Syncs ride coverage by scanning recent messages in relevant channels.
        Also cleans up entries for messages that no longer exist.

        Returns:
            dict: Summary of the sync operation.
        """
        logger.info("sync_ride_coverage: Starting sync of recent messages...")

        channels_to_scan = [
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        ]

        total_messages_scanned = 0
        total_entries_added = 0
        total_entries_removed = 0
        since = get_last_sunday()

        # Collect all valid message IDs we find during scan
        valid_message_ids = set()

        for channel_id in channels_to_scan:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"sync_ride_coverage: Could not find channel {channel_id}")
                continue

            logger.info(
                f"sync_ride_coverage: Scanning channel {channel.name} (id={channel_id}) "
                f"since {since}"
            )

            try:
                async for message in channel.history(after=since, limit=500):
                    total_messages_scanned += 1
                    valid_message_ids.add(str(message.id))

                    if message.author.bot:
                        continue

                    if not self._is_grouping_message(message):
                        continue

                    passenger_usernames = self._extract_passengers(message)

                    if passenger_usernames:
                        try:
                            await self.repo.add_coverage_entries(
                                passenger_usernames, str(message.id)
                            )
                            total_entries_added += len(passenger_usernames)
                        except Exception as e:
                            # Likely duplicate key error, which is fine
                            logger.debug(f"sync_ride_coverage: Entry may already exist: {e}")

            except Exception as e:
                logger.error(f"sync_ride_coverage: Error scanning channel {channel_id}: {e}")

        # Clean up entries for messages that no longer exist
        logger.info("sync_ride_coverage: Checking for orphaned entries...")
        try:
            db_message_ids = await self.repo.get_unique_message_ids(since)
            orphaned_ids = db_message_ids - valid_message_ids

            for orphaned_id in orphaned_ids:
                logger.info(
                    f"sync_ride_coverage: Removing entries for deleted message {orphaned_id}"
                )
                deleted = await self.repo.delete_all_entries_by_message(orphaned_id)
                total_entries_removed += deleted

            if orphaned_ids:
                logger.info(
                    f"sync_ride_coverage: Cleaned up {total_entries_removed} orphaned entries "
                    f"from {len(orphaned_ids)} deleted messages"
                )

        except Exception as e:
            logger.error(f"sync_ride_coverage: Error during orphan cleanup: {e}")

        logger.info(
            f"sync_ride_coverage: Completed. Scanned {total_messages_scanned} messages, "
            f"added {total_entries_added} entries, removed {total_entries_removed} orphaned entries"
        )

        return {
            "messages_scanned": total_messages_scanned,
            "entries_added": total_entries_added,
            "entries_removed": total_entries_removed,
            "since": str(since),
        }

    def _is_grouping_message(self, message: discord.Message) -> bool:
        """Checks if a message is a ride grouping message."""
        # Check if it's in a relevant channel and has the grouping prefix
        if message.channel.id not in [
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
            ChannelIds.BOT_STUFF__BOT_SPAM_2,  # For testing
        ]:
            logger.debug(f"Message {message.id} not in allowed channels, skipping")
            return False

        has_drive = "drive:" in message.content.lower()
        logger.debug(f"Message {message.id} has 'drive:': {has_drive}")
        return has_drive

    def _extract_passengers(self, message: discord.Message) -> list[str]:
        """Extracts passenger usernames from a grouping message."""
        content = message.content
        drive_idx = content.lower().find("drive:")
        if drive_idx == -1:
            logger.debug(f"Message {message.id}: 'drive:' not found in content")
            return []

        passengers = []
        logger.debug(f"Message {message.id}: Found {len(message.mentions)} mentions")

        for user in message.mentions:
            # Handle both <@id> and <@!id>
            if any(m in content[drive_idx:] for m in (f"<@{user.id}>", f"<@!{user.id}>")):
                passengers.append(str(user))
                logger.debug(f"Message {message.id}: Added passenger {user}")
            else:
                logger.debug(f"Message {message.id}: User {user} not in 'drive:' section")

        logger.debug(f"Message {message.id}: Extracted passengers: {passengers}")
        return passengers

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listener for new messages to detect ride coverage."""
        if message.author.bot:
            return

        logger.debug(f"on_message: Received message {message.id} from {message.author}")

        if not self._is_grouping_message(message):
            return

        logger.debug(f"on_message: Message {message.id} is a grouping message")

        passenger_usernames = self._extract_passengers(message)

        if passenger_usernames:
            logger.info(
                f"on_message: Detected ride coverage for: {passenger_usernames} "
                f"(message_id={message.id})"
            )

            try:
                await self.repo.add_coverage_entries(passenger_usernames, str(message.id))
                logger.info(
                    f"on_message: Successfully added {len(passenger_usernames)} coverage entries"
                )
            except Exception as e:
                logger.error(f"on_message: Failed to record ride coverage: {e}")
        else:
            logger.debug(f"on_message: No passengers found in message {message.id}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Listener for message edit events to sync ride coverage."""
        if after.author.bot:
            return

        logger.debug(f"on_message_edit: Message {after.id} edited by {after.author}")

        if not self._is_grouping_message(after):
            logger.debug(f"on_message_edit: Message {after.id} is not a grouping message, skipping")
            return

        logger.debug(f"on_message_edit: Message {after.id} is a grouping message, processing edit")

        before_passengers = set(self._extract_passengers(before))
        after_passengers = set(self._extract_passengers(after))

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
                await self.repo.add_coverage_entries(list(added), str(after.id))
                logger.info(f"on_message_edit: Successfully added {len(added)} coverage entries")
            except Exception as e:
                logger.error(f"on_message_edit: Failed to add ride coverage on edit: {e}")

        if removed:
            logger.info(
                f"on_message_edit: Ride coverage removed via edit: {list(removed)} "
                f"(message_id={after.id})"
            )

            try:
                await self.repo.delete_coverage_entries(list(removed), str(after.id))
                logger.info(
                    f"on_message_edit: Successfully removed {len(removed)} coverage entries"
                )
            except Exception as e:
                logger.error(f"on_message_edit: Failed to remove ride coverage on edit: {e}")

        if not added and not removed:
            logger.debug(f"on_message_edit: No passenger changes detected for message {after.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Listener for message delete events to remove ride coverage."""
        logger.debug(f"on_message_delete: Message {message.id} deleted by {message.author}")

        # Check if this was potentially a grouping message
        # Note: We check all channels since we can't verify content after deletion
        if message.channel.id not in [
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
            ChannelIds.BOT_STUFF__BOT_SPAM_2,  # For testing
        ]:
            return

        # Try to delete any coverage entries for this message
        try:
            deleted_count = await self.repo.delete_all_entries_by_message(str(message.id))
            if deleted_count > 0:
                logger.info(
                    f"on_message_delete: Removed {deleted_count} coverage entries "
                    f"for deleted message {message.id}"
                )

            else:
                logger.debug(
                    f"on_message_delete: No coverage entries found for message {message.id}"
                )
        except Exception as e:
            logger.error(f"on_message_delete: Failed to remove coverage entries: {e}")


async def setup(bot: commands.Bot):
    """Sets up the RideCoverage cog."""
    await bot.add_cog(RideCoverage(bot))
