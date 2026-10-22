"""Service for ride coverage business logic."""

import logging

import discord

from ridebot.utils.time_helpers import (
    is_in_coverage_widget_window,
)
from shared.core.enums import ChannelIds

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
        from ridebot.services.ride_event_sync_service import RideEventSyncService
        from ridebot.services.ride_events_service import RideEventsService

        await RideEventSyncService(self.bot).run(discover=True)
        targets = await RideEventsService.sync_targets()
        return {"synced": len(targets), "entries_added": 0, "entries_removed": 0}

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
        from ridebot.services.ride_events_service import RideEventsService

        event = await RideEventsService.resolve_event(day=ride_type)
        if event is None:
            return {
                "users": [],
                "total": 0,
                "assigned": 0,
                "message_found": False,
                "has_coverage_entries": False,
                "is_in_visibility_window": is_in_coverage_widget_window(ride_type),
            }
        workflow = await RideEventsService.workflow(event.id)
        _, requests, roster, offers, assignments, state = workflow
        if ride_type == "sunday":
            class_event = await RideEventsService.resolve_event(day="sunday_class")
            if class_event and class_event.event_date == event.event_date:
                class_workflow = await RideEventsService.workflow(class_event.id)
                class_identities = (
                    {r.identity_key for r in class_workflow[1]} if class_workflow else set()
                )
                requests = [r for r in requests if r.identity_key not in class_identities]
        offer_map = {o.id: o for o in offers}
        assigned_ids = {
            a.request_id
            for a in assignments
            if a.direction == "pickup"
            and a.driver_offer_id in offer_map
            and offer_map[a.driver_offer_id].availability == "available"
        }
        users = []
        for row in requests:
            if not row.pickup:
                continue
            person = roster.get(row.discord_user_id)
            users.append(
                {
                    "discord_username": person.discord_username
                    if person and person.discord_username
                    else row.name,
                    "has_ride": row.id in assigned_ids,
                }
            )
        users.sort(key=lambda row: (row["has_ride"], row["discord_username"]))
        assigned = sum(u["has_ride"] for u in users)
        return {
            "users": users,
            "total": len(users),
            "assigned": assigned,
            "message_found": True,
            "has_coverage_entries": assigned > 0,
            "is_in_visibility_window": is_in_coverage_widget_window(ride_type),
            "event_id": event.id,
            "freshness": state,
        }
