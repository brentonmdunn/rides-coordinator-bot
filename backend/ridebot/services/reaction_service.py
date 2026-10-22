"""Compatibility selectors backed by durable event state, never live Discord reads."""

from ridebot.services.ride_events_service import RideEventsService
from ridebot.utils.cache import alru_cache
from shared.core.enums import AskRidesMessage, CacheNamespace, ChannelIds, Emoji, RideOption


class ReactionService:
    """Expose stored message/reaction views to existing commands and dashboards."""

    def __init__(self, bot=None):
        """Retain the constructor shape while reads remain independent of the bot."""
        self.bot = bot

    @alru_cache(ttl=0, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_REACTIONS)
    async def get_usernames_who_reacted(self, channel_id, message_id, option=None):
        """Read saved choices, retaining legacy Sunday return filters."""
        choices = await RideEventsService.message_choices(message_id, channel_id)
        skipped = set()
        if option == RideOption.SUNDAY_DROPOFF_BACK:
            skipped = {Emoji.LUNCH, Emoji.SOMETHING_ELSE}
        elif option == RideOption.SUNDAY_DROPOFF_LUNCH:
            skipped = {Emoji.NO_LUNCH, Emoji.SOMETHING_ELSE}
        return {row.discord_username for row in choices if row.emoji not in skipped}

    @alru_cache(ttl=0, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_REACTIONS)
    async def get_ask_rides_reactions(self, event):
        """Return recorded rider reactions and source freshness."""
        return await RideEventsService.breakdown(event, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)

    @alru_cache(ttl=0, ignore_self=True, namespace=CacheNamespace.ASK_DRIVERS_REACTIONS)
    async def get_driver_reactions(self, event):
        """Return recorded driver choices without a gateway connection."""
        if event not in (AskRidesMessage.FRIDAY_FELLOWSHIP, AskRidesMessage.SUNDAY_SERVICE):
            raise ValueError(f"Invalid event for driver reactions: {event}")
        return await RideEventsService.breakdown(
            event, ChannelIds.SERVING__DRIVER_CHAT_WOOOOO, kind="driver"
        )

    async def get_drive_back_usernames(self, channel_id, message_id):
        """Read saved drive-back choices for a source message."""
        return {
            row.discord_username
            for row in await RideEventsService.message_choices(message_id, channel_id)
            if row.emoji == Emoji.DRIVE_BACK
        }

    @alru_cache(ttl=0, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def find_correct_message(self, ask_rides_message, channel_id):
        """Resolve an explicit current-cycle rider source mapping."""
        return await RideEventsService.current_message(ask_rides_message, channel_id)

    async def _find_all_messages(self, channel_id):
        """Read mappings without scanning channel history."""
        return {
            event: await self.find_correct_message(event, channel_id) for event in AskRidesMessage
        }

    @alru_cache(ttl=0, ignore_self=True, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def find_driver_message(self, event, channel_id=ChannelIds.SERVING__DRIVER_CHAT_WOOOOO):
        """Resolve a current-cycle driver source mapping."""
        return await RideEventsService.current_message(event, channel_id, kind="driver")

    async def _find_all_driver_messages(self, channel_id=ChannelIds.SERVING__DRIVER_CHAT_WOOOOO):
        """Read driver mappings without Discord history scans."""
        return {
            event: await self.find_driver_message(event, channel_id) for event in AskRidesMessage
        }
