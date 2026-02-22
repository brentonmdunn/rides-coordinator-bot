"""Cog for handling reactions."""

import discord
from discord.ext import commands

from bot.cogs.locations import Locations
from bot.core.enums import (
    AskRidesMessage,
    ChannelIds,
    DaysOfWeek,
    FeatureFlagNames,
)
from bot.core.logger import logger
from bot.core.reaction_enums import ReactionAction
from bot.repositories.thread_repository import EventThreadRepository
from bot.services.reaction_logging_service import ReactionLoggingService
from bot.services.ride_request_service import RideRequestService
from bot.services.thread_service import ThreadService
from bot.utils.checks import feature_flag_enabled
from bot.utils.parsing import get_message_and_embed_content
from bot.utils.time_helpers import is_during_target_window


class Reactions(commands.Cog):
    """Cog for handling reaction events on Discord messages.

    This cog monitors reaction additions and removals to trigger various automated
    behaviors such as logging reactions, managing event threads, creating ride
    coordination channels, and notifying about late ride requests.

    Attributes:
        bot: The Discord bot instance.
        locations_cog: Reference to the Locations cog for location lookups.
        thread_service: Service for managing event thread operations.
        logging_service: Service for logging reaction events.
        ride_request_service: Service for managing ride request channels.
    """

    def __init__(
        self,
        bot: commands.Bot,
        thread_service: ThreadService,
        logging_service: ReactionLoggingService,
        ride_request_service: RideRequestService,
    ):
        """Initialize the Reactions cog.

        Args:
            bot: The Discord bot instance.
            thread_service: Service for thread management.
            logging_service: Service for reaction logging.
            ride_request_service: Service for ride request handling.
        """
        self.bot = bot
        self.locations_cog: Locations | None = None
        self.thread_service = thread_service
        self.logging_service = logging_service
        self.ride_request_service = ride_request_service

    async def cog_load(self):
        """Wait until the bot is ready to get the cog."""
        self.locations_cog = self.bot.get_cog("Locations")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is added to a message."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return  # DM or unknown guild

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return  # Ensure it's a text channel

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)

        if user and user.bot:
            logger.info(f"Ignoring bot reaction from {user.name}")
            return

        if not user:
            return

        await self._late_rides_react(user, payload, message, channel, ReactionAction.ADD)
        await self._log_reactions(user, payload, message, channel, ReactionAction.ADD)
        await self._new_rides_helper(user, guild, payload.message_id)
        await self._event_thread_add(payload, guild, user)
        await self._check_if_ask_message(payload.message_id, payload.channel_id)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is removed from a message."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)

        if user and user.bot:
            logger.info(f"Ignoring bot reaction removal from {user.name}")
            return

        await self._late_rides_react(user, payload, message, channel, ReactionAction.REMOVE)
        await self._log_reactions(user, payload, message, channel, ReactionAction.REMOVE)
        await self._event_thread_remove(payload, guild)
        await self._check_if_ask_message(payload.message_id, payload.channel_id)

    async def _check_if_ask_message(self, message_id, channel_id):
        from bot.services.locations_service import LocationsService
        from bot.utils.cache import (
            warm_ask_drivers_reactions_cache,
            warm_ask_rides_reactions_cache,
        )

        if channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS:
            locations_svc = LocationsService(self.bot)
            for event in AskRidesMessage:
                m_id = await locations_svc._find_correct_message(event, channel_id)
                if m_id == message_id:
                    await warm_ask_rides_reactions_cache(self.bot, event)
                    break

        elif channel_id == ChannelIds.SERVING__DRIVER_CHAT_WOOOOO:
            locations_svc = LocationsService(self.bot)
            for event in AskRidesMessage:
                m_id = await locations_svc._find_driver_message(event, channel_id)
                if m_id == message_id:
                    await warm_ask_drivers_reactions_cache(self.bot, event)
                    break

    @feature_flag_enabled(FeatureFlagNames.EVENT_THREADS)
    async def _event_thread_add(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild, user: discord.Member
    ):
        """Add a user to an event thread when they react to the thread's starter message.

        This method checks if the reacted message is associated with an event thread.
        If so, it automatically adds the reacting user to that thread.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction occurred.
            user: The user who added the reaction.

        Note:
            This method is only active when the EVENT_THREADS feature flag is enabled.
        """
        await self.thread_service.add_reactor_to_thread(payload, guild, user)

    @feature_flag_enabled(FeatureFlagNames.EVENT_THREADS)
    async def _event_thread_remove(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild
    ):
        """Remove a user from an event thread when they remove all their reactions.

        This method checks if the reacted message is associated with an event thread.
        If the user has no remaining reactions on the message, they are removed from
        the thread.

        Args:
            payload: The raw reaction event payload containing message and emoji info.
            guild: The Discord guild where the reaction was removed.

        Note:
            This method is only active when the EVENT_THREADS feature flag is enabled.
            Users are only removed if they have zero reactions remaining on the message.
        """
        await self.thread_service.remove_reactor_from_thread(payload, guild, self.bot)

    @feature_flag_enabled(FeatureFlagNames.LATE_RIDES_REACT)
    async def _late_rides_react(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        channel: discord.TextChannel,
        action: ReactionAction,
    ):
        """Log late ride reactions during specific time windows.

        Monitors reactions to ride announcement messages during target time windows
        (Friday, Sunday, or Wednesday) and logs them to the driver bot spam channel.

        Args:
            user: The user who reacted.
            payload: The raw reaction event payload.
            message: The message that was reacted to.
            channel: The channel where the message was sent.
            action: Whether the reaction was added or removed.

        Note:
            This method is only active when the LATE_RIDES_REACT feature flag is enabled.
            Only logs reactions in the rides announcements channel during target windows.
        """
        message_content = get_message_and_embed_content(message)
        if payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS and (
            ("friday" in message_content and is_during_target_window(DaysOfWeek.FRIDAY))
            or ("sunday" in message_content and is_during_target_window(DaysOfWeek.SUNDAY))
            or ("wednesday" in message_content and is_during_target_window(DaysOfWeek.WEDNESDAY))
        ):
            await self.logging_service.log_late_ride_reaction(user, payload, message, action)

    @feature_flag_enabled(FeatureFlagNames.LOG_REACTIONS, enable_logs=False)
    async def _log_reactions(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        channel: discord.TextChannel,
        action: ReactionAction,
    ):
        """Log all reaction events to the bot logs channel.

        Sends a formatted log message to the bot logs channel whenever a reaction
        is added or removed from any message.

        Args:
            user: The user who reacted.
            payload: The raw reaction event payload.
            message: The message that was reacted to.
            channel: The channel where the message was sent.
            action: Whether the reaction was added or removed.

        Note:
            This method is only active when the LOG_REACTIONS feature flag is enabled.
        """
        await self.logging_service.log_reaction(user, payload, message, channel, action)

    @feature_flag_enabled(FeatureFlagNames.NEW_RIDES_MSG)
    async def _new_rides_helper(self, user: discord.Member, guild: discord.Guild, message_id: int):
        """Create a private channel for new riders who need location information.

        When a user without a registered location reacts to a ride announcement,
        this creates a private channel where ride coordinators can collect their
        location information.

        Args:
            user: The user who reacted to the ride announcement.
            guild: The Discord guild where the reaction occurred.
            message_id: The ID of the message that was reacted to.

        Note:
            This method is only active when the NEW_RIDES_MSG feature flag is enabled.
            Only creates channels for users without registered locations who react
            to Friday Fellowship or Sunday Service ride announcements.
        """
        # Check if this is a valid ride announcement reaction
        if not (
            (
                self.locations_cog
                and (
                    message_id
                    == await self.locations_cog.service._find_correct_message(
                        AskRidesMessage.FRIDAY_FELLOWSHIP,
                        ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
                    )
                    or message_id
                    == await self.locations_cog.service._find_correct_message(
                        AskRidesMessage.SUNDAY_SERVICE, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
                    )
                )
            )
            and user is not None
            and (
                self.locations_cog
                and not await self.locations_cog.service.get_location(user.name, discord_only=True)
            )
        ):
            return

        # Delegate to service
        await self.ride_request_service.handle_new_rider_reaction(user, guild)


async def setup(bot: commands.Bot):
    """Add the Reactions cog to the bot.

    Args:
        bot: The Discord bot instance to add the cog to.
    """
    # Initialize repository (only for database operations)
    thread_repository = EventThreadRepository()

    # Initialize services
    thread_service = ThreadService(thread_repository)
    logging_service = ReactionLoggingService(bot)
    ride_request_service = RideRequestService(bot)

    # Add cog with dependency injection
    await bot.add_cog(Reactions(bot, thread_service, logging_service, ride_request_service))
