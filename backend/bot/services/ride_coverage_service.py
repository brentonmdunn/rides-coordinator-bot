"""Service for ride coverage business logic."""

import logging

import discord

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AskRidesMessage, ChannelIds, JobName
from bot.core.error_reporter import send_error_to_discord
from bot.repositories.ride_coverage_repository import RideCoverageRepository
from bot.utils.time_helpers import get_last_sunday

logger = logging.getLogger(__name__)


class RideCoverageService:
    """Business logic for ride coverage tracking."""

    def __init__(self, bot):
        """Initialize the RideCoverageService."""
        self.bot = bot

    async def sync_ride_coverage(self) -> dict:
        """
        Sync ride coverage by scanning recent messages in relevant channels.
        Also cleans up entries for messages that no longer exist.

        Returns:
            dict: Summary of the sync operation.
        """
        logger.info("sync_ride_coverage: Starting sync of recent messages...")

        channels_to_scan = [ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS]

        total_messages_scanned = 0
        total_entries_added = 0
        total_entries_removed = 0
        since = get_last_sunday()
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

                    if not self.is_grouping_message(message):
                        continue

                    passenger_usernames = self.extract_passengers(message)

                    if passenger_usernames:
                        try:
                            async with AsyncSessionLocal() as session:
                                await RideCoverageRepository.add_coverage_entries(
                                    session, passenger_usernames, str(message.id)
                                )
                            total_entries_added += len(passenger_usernames)
                        except Exception as e:
                            logger.debug(f"sync_ride_coverage: Entry may already exist: {e}")

            except Exception:
                logger.exception(f"sync_ride_coverage: Error scanning channel {channel_id}")
                await send_error_to_discord(
                    f"**Unexpected Error** in `sync_ride_coverage` scanning channel `{channel_id}`"
                )

        logger.info("sync_ride_coverage: Checking for orphaned entries...")
        try:
            async with AsyncSessionLocal() as session:
                db_message_ids = await RideCoverageRepository.get_unique_message_ids(session, since)
            orphaned_ids = db_message_ids - valid_message_ids

            for orphaned_id in orphaned_ids:
                logger.info(
                    f"sync_ride_coverage: Removing entries for deleted message {orphaned_id}"
                )
                async with AsyncSessionLocal() as session:
                    deleted = await RideCoverageRepository.delete_all_entries_by_message(
                        session, orphaned_id
                    )
                total_entries_removed += deleted

            if orphaned_ids:
                logger.info(
                    f"sync_ride_coverage: Cleaned up {total_entries_removed} orphaned entries "
                    f"from {len(orphaned_ids)} deleted messages"
                )

        except Exception:
            logger.exception("sync_ride_coverage: Error during orphan cleanup")
            await send_error_to_discord(
                "**Unexpected Error** in `sync_ride_coverage` orphan cleanup"
            )

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

    @staticmethod
    def is_grouping_message(message: discord.Message) -> bool:
        """Check if a message is a ride grouping message."""
        if message.channel.id not in [
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
            ChannelIds.BOT_STUFF__BOT_SPAM_2,
        ]:
            logger.debug(f"Message {message.id} not in allowed channels, skipping")
            return False

        has_drive = "drive:" in message.content.lower()
        logger.debug(f"Message {message.id} has 'drive:': {has_drive}")
        return has_drive

    @staticmethod
    def extract_passengers(message: discord.Message) -> list[str]:
        """Extract passenger usernames from a grouping message."""
        content = message.content
        drive_idx = content.lower().find("drive:")
        if drive_idx == -1:
            logger.debug(f"Message {message.id}: 'drive:' not found in content")
            return []

        passengers = []
        logger.debug(f"Message {message.id}: Found {len(message.mentions)} mentions")

        for user in message.mentions:
            if any(m in content[drive_idx:] for m in (f"<@{user.id}>", f"<@!{user.id}>")):
                passengers.append(str(user))
                logger.debug(f"Message {message.id}: Added passenger {user}")
            else:
                logger.debug(f"Message {message.id}: User {user} not in 'drive:' section")

        logger.debug(f"Message {message.id}: Extracted passengers: {passengers}")
        return passengers

    async def get_coverage_summary(self, ride_type: str) -> dict:
        """
        Get ride coverage summary for users who reacted to a ride message.

        Args:
            ride_type: "friday" or "sunday"

        Returns:
            Dict with users, total, assigned, message_found, has_coverage_entries.
        """
        from bot.services.locations_service import LocationsService

        locations_service = LocationsService(self.bot)

        if ride_type.lower() == JobName.FRIDAY:
            ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
        else:
            ask_message = AskRidesMessage.SUNDAY_SERVICE

        message_id = await locations_service.find_correct_message(
            ask_message, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        )

        if message_id is None:
            return {
                "users": [],
                "total": 0,
                "assigned": 0,
                "message_found": False,
                "has_coverage_entries": False,
            }

        usernames_reacted = await locations_service.get_usernames_who_reacted(
            int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS), message_id
        )

        if ride_type.lower() == JobName.SUNDAY:
            class_message_id = await locations_service.find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )
            if class_message_id:
                class_usernames = await locations_service.get_usernames_who_reacted(
                    int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS), class_message_id
                )
                usernames_reacted -= class_usernames

        last_sunday = get_last_sunday()
        usernames_list = [str(u) for u in usernames_reacted]
        async with AsyncSessionLocal() as session:
            covered_usernames = await RideCoverageRepository.get_bulk_coverage_status(
                session, usernames_list, since=last_sunday
            )

        users = []
        assigned_count = 0
        for username in usernames_list:
            has_ride = username in covered_usernames
            if has_ride:
                assigned_count += 1
            users.append({"discord_username": username, "has_ride": has_ride})

        users.sort(key=lambda x: (x["has_ride"], x["discord_username"]))

        return {
            "users": users,
            "total": len(users),
            "assigned": assigned_count,
            "message_found": True,
            "has_coverage_entries": assigned_count > 0,
        }
