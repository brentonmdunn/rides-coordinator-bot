"""Cog for handling reactions."""

import logging

import discord
from discord.ext import commands

from ridebot.cogs.locations import Locations
from ridebot.services.late_reaction_windows_service import LateReactionWindowsService
from ridebot.services.reaction_logging_service import ReactionLoggingService
from ridebot.services.ride_reaction_log_service import RideReactionLogService
from ridebot.services.ride_request_service import RideRequestService
from ridebot.services.roster_service import RosterService
from ridebot.utils.parsing import get_message_and_embed_content
from ridebot.utils.time_helpers import is_during_late_reaction_window
from ridebot.views.pickup_info import PickupInfoView
from shared.core.enums import (
    AskRidesMessage,
    ChannelIds,
    FeatureFlagNames,
    ReactionAction,
)
from shared.core.logger import generate_txn_id, txn_id_var
from shared.utils.checks import feature_flag_enabled

logger = logging.getLogger(__name__)


class Reactions(commands.Cog):
    """
    Cog for handling reaction events on Discord messages.

    This cog monitors reaction additions and removals to trigger various automated
    behaviors such as logging reactions, creating ride coordination channels, and
    notifying about late ride requests.

    Attributes:
        bot: The Discord bot instance.
        locations_cog: Reference to the Locations cog for location lookups.
        logging_service: Service for logging reaction events.
        ride_request_service: Service for managing ride request channels.
    """

    def __init__(
        self,
        bot: commands.Bot,
        logging_service: ReactionLoggingService,
        ride_request_service: RideRequestService,
    ):
        """
        Initialize the Reactions cog.

        Args:
            bot: The Discord bot instance.
            logging_service: Service for reaction logging.
            ride_request_service: Service for ride request handling.
        """
        self.bot = bot
        self.locations_cog: Locations | None = None
        self.logging_service = logging_service
        self.ride_request_service = ride_request_service

    async def cog_load(self):
        """Wait until the bot is ready to get the cog, and register persistent views."""
        cog = self.bot.get_cog("Locations")
        self.locations_cog = cog if isinstance(cog, Locations) else None
        self.bot.add_view(PickupInfoView())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is added to a message."""
        txn_token = txn_id_var.set(generate_txn_id())
        try:
            await self._handle_reaction_add(payload)
        finally:
            txn_id_var.reset(txn_token)

    async def _handle_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Inner handler for reaction add, runs under a transaction ID."""
        logger.debug(
            "_handle_reaction_add: guild_id=%s channel_id=%s message_id=%s user_id=%s emoji=%s",
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            payload.emoji,
        )
        if payload.guild_id is None:
            logger.debug("_handle_reaction_add: guild_id is None, skipping")
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.debug("_handle_reaction_add: guild not found, skipping")
            return  # DM or unknown guild

        channel = self.bot.get_channel(payload.channel_id)
        logger.debug(
            "_handle_reaction_add: channel=%r type=%s",
            channel,
            type(channel).__name__,
        )
        if not isinstance(channel, discord.TextChannel):
            logger.debug(
                "_handle_reaction_add: channel is not TextChannel (got %s), skipping",
                type(channel).__name__,
            )
            return  # Ensure it's a text channel

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)
        logger.debug(
            "_handle_reaction_add: user=%s bot=%s",
            getattr(user, "name", None),
            getattr(user, "bot", None),
        )

        if user and user.bot:
            logger.info(f"Ignoring bot reaction from {user.name}")
            return

        if not user:
            logger.debug("_handle_reaction_add: user not found in guild cache, skipping")
            return

        try:
            await self._late_rides_react(user, payload, message, channel, ReactionAction.ADD)
        except Exception:
            logger.exception("_handle_reaction_add: error in _late_rides_react")

        try:
            await self._log_reactions(user, payload, message, channel, ReactionAction.ADD)
        except Exception:
            logger.exception("_handle_reaction_add: error in _log_reactions")

        try:
            await self._new_rides_helper(user, guild, payload.message_id)
        except Exception:
            logger.exception("_handle_reaction_add: error in _new_rides_helper")

        try:
            await self._check_if_ask_message(payload.message_id, payload.channel_id)
        except Exception:
            logger.exception("_handle_reaction_add: error in _check_if_ask_message")

        try:
            await self._record_ask_rides_reaction(user, payload, message, ReactionAction.ADD)
        except Exception:
            logger.exception("_handle_reaction_add: error in _record_ask_rides_reaction")

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handles when a reaction is removed from a message."""
        txn_token = txn_id_var.set(generate_txn_id())
        try:
            await self._handle_reaction_remove(payload)
        finally:
            txn_id_var.reset(txn_token)

    async def _handle_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Inner handler for reaction remove, runs under a transaction ID."""
        logger.debug(
            "_handle_reaction_remove: guild_id=%s channel_id=%s message_id=%s user_id=%s emoji=%s",
            payload.guild_id,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            payload.emoji,
        )
        if payload.guild_id is None:
            logger.debug("_handle_reaction_remove: guild_id is None, skipping")
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            logger.debug("_handle_reaction_remove: guild not found, skipping")
            return

        channel = self.bot.get_channel(payload.channel_id)
        logger.debug(
            "_handle_reaction_remove: channel=%r type=%s",
            channel,
            type(channel).__name__,
        )
        if not isinstance(channel, discord.TextChannel):
            logger.debug(
                "_handle_reaction_remove: channel is not TextChannel (got %s), skipping",
                type(channel).__name__,
            )
            return

        message = await channel.fetch_message(payload.message_id)
        user = guild.get_member(payload.user_id)
        logger.debug(
            "_handle_reaction_remove: user=%s bot=%s",
            getattr(user, "name", None),
            getattr(user, "bot", None),
        )

        if user and user.bot:
            logger.info(f"Ignoring bot reaction removal from {user.name}")
            return

        if not user:
            logger.debug("_handle_reaction_remove: user not found in guild cache, skipping")
            return

        try:
            await self._late_rides_react(user, payload, message, channel, ReactionAction.REMOVE)
        except Exception:
            logger.exception("_handle_reaction_remove: error in _late_rides_react")

        try:
            await self._log_reactions(user, payload, message, channel, ReactionAction.REMOVE)
        except Exception:
            logger.exception("_handle_reaction_remove: error in _log_reactions")

        try:
            await self._check_if_ask_message(payload.message_id, payload.channel_id)
        except Exception:
            logger.exception("_handle_reaction_remove: error in _check_if_ask_message")

        try:
            await self._record_ask_rides_reaction(user, payload, message, ReactionAction.REMOVE)
        except Exception:
            logger.exception("_handle_reaction_remove: error in _record_ask_rides_reaction")

    async def _record_ask_rides_reaction(
        self,
        user: discord.Member | None,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        action: ReactionAction,
    ) -> None:
        """
        Persist a reaction event on the rides announcements channel to the database.

        Args:
            user: The member who reacted, or None if unavailable.
            payload: The raw reaction event payload.
            message: The message that was reacted to.
            action: Whether the reaction was added or removed.
        """
        logger.debug(
            "_record_ask_rides_reaction: user=%s action=%s channel_id=%s expected=%s",
            getattr(user, "name", None),
            action,
            payload.channel_id,
            ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS.value,
        )
        if user is None:
            logger.debug("_record_ask_rides_reaction: user is None, skipping")
            return
        if payload.channel_id == ChannelIds.SERVING__DRIVER_CHAT_WOOOOO:
            logger.debug("_record_ask_rides_reaction: broadcasting driver-chat reaction")
            await RideReactionLogService.broadcast_driver_chat_reaction(user, payload, action)
            return
        if payload.channel_id != ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS:
            logger.debug(
                "_record_ask_rides_reaction: channel mismatch (%s != %s), skipping",
                payload.channel_id,
                ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS.value,
            )
            return
        logger.debug("_record_ask_rides_reaction: calling RideReactionLogService")
        await RideReactionLogService.record_ask_rides_reaction(user, payload, message, action)

    async def _check_if_ask_message(self, message_id, channel_id):
        from ridebot.utils.cache import (
            warm_ask_drivers_reactions_cache,
            warm_ask_rides_reactions_cache,
        )

        if not self.locations_cog:
            return

        locations_svc = self.locations_cog.service

        if channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS:
            for event in AskRidesMessage:
                m_id = await locations_svc.find_correct_message(event, channel_id)
                if m_id == message_id:
                    await warm_ask_rides_reactions_cache(self.bot, event)
                    break

        elif channel_id == ChannelIds.SERVING__DRIVER_CHAT_WOOOOO:
            for event in AskRidesMessage:
                m_id = await locations_svc._find_driver_message(event, channel_id)
                if m_id == message_id:
                    await warm_ask_drivers_reactions_cache(self.bot, event)
                    break

    @feature_flag_enabled(FeatureFlagNames.LATE_RIDES_REACT)
    async def _late_rides_react(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        channel: discord.TextChannel,
        action: ReactionAction,
    ):
        """
        Log late ride reactions during specific time windows.

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
        if payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS:
            windows = await LateReactionWindowsService.get_windows()
            if is_during_late_reaction_window(message_content, windows):
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
        """
        Log all reaction events to the bot logs channel.

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
        """
        Create a private channel for new riders who need location information.

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
                    == await self.locations_cog.service.find_correct_message(
                        AskRidesMessage.FRIDAY_FELLOWSHIP,
                        ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
                    )
                    or message_id
                    == await self.locations_cog.service.find_correct_message(
                        AskRidesMessage.SUNDAY_SERVICE, ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
                    )
                )
            )
            and user is not None
            and await RosterService.find_member(discord_user_id=user.id, discord_username=user.name)
            is None
        ):
            return

        # Delegate to service
        await self.ride_request_service.handle_new_rider_reaction(user, guild)


async def setup(bot: commands.Bot):
    """
    Add the Reactions cog to the bot.

    Args:
        bot: The Discord bot instance to add the cog to.
    """
    logging_service = ReactionLoggingService(bot)
    ride_request_service = RideRequestService(bot)

    # Add cog with dependency injection
    await bot.add_cog(Reactions(bot, logging_service, ride_request_service))
