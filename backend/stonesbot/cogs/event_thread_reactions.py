"""Cog for adding/removing reactors to event threads."""

import logging

import discord
from discord.ext import commands

from shared.core.enums import FeatureFlagNames
from shared.core.logger import generate_txn_id, txn_id_var
from shared.utils.checks import feature_flag_enabled
from stonesbot.services.thread_service import ThreadService

logger = logging.getLogger(__name__)


class EventThreadReactions(commands.Cog):
    """
    Cog for handling reaction events that manage event thread membership.

    This cog monitors reaction additions and removals on Discord messages to
    automatically add and remove users from their associated event threads.

    Attributes:
        bot: The Discord bot instance.
        thread_service: Service for managing event thread operations.
    """

    def __init__(self, bot: commands.Bot, thread_service: ThreadService):
        """
        Initialize the EventThreadReactions cog.

        Args:
            bot: The Discord bot instance.
            thread_service: Service for thread management.
        """
        self.bot = bot
        self.thread_service = thread_service

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

        user = guild.get_member(payload.user_id)
        logger.debug(
            "_handle_reaction_add: user=%s bot=%s",
            getattr(user, "name", None),
            getattr(user, "bot", None),
        )

        if not user:
            logger.debug("_handle_reaction_add: user not found in guild cache, skipping")
            return

        if user.bot:
            logger.info(f"Ignoring bot reaction from {user.name}")
            return

        try:
            await self._event_thread_add(payload, guild, user)
        except Exception:
            logger.exception("_handle_reaction_add: error in _event_thread_add")

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

        user = guild.get_member(payload.user_id)
        logger.debug(
            "_handle_reaction_remove: user=%s bot=%s",
            getattr(user, "name", None),
            getattr(user, "bot", None),
        )

        if not user:
            logger.debug("_handle_reaction_remove: user not found in guild cache, skipping")
            return

        if user.bot:
            logger.info(f"Ignoring bot reaction removal from {user.name}")
            return

        try:
            await self._event_thread_remove(payload, guild)
        except Exception:
            logger.exception("_handle_reaction_remove: error in _event_thread_remove")

    @feature_flag_enabled(FeatureFlagNames.EVENT_THREADS)
    async def _event_thread_add(
        self, payload: discord.RawReactionActionEvent, guild: discord.Guild, user: discord.Member
    ):
        """
        Add a user to an event thread when they react to the thread's starter message.

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
        """
        Remove a user from an event thread when they remove all their reactions.

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


async def setup(bot: commands.Bot):
    """
    Add the EventThreadReactions cog to the bot.

    Args:
        bot: The Discord bot instance to add the cog to.
    """
    thread_service = ThreadService()
    await bot.add_cog(EventThreadReactions(bot, thread_service))
