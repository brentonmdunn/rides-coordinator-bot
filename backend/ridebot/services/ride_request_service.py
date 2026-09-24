"""Service for handling ride requests."""

import asyncio
import logging
import time
from collections import defaultdict
from typing import Any, cast

import discord

from ridebot.utils.constants import (
    NEW_RIDER_CHANNEL_MEMORY_SECONDS,
    PICKUP_INFO_BUTTON_CUSTOM_IDS,
)
from ridebot.views.pickup_info import PickupInfoView
from shared.core.enums import CategoryIds, ChannelIds, RoleIds
from shared.core.error_reporter import send_error_to_discord

logger = logging.getLogger(__name__)

# Module-level so every RideRequestService instance shares them. Reactions arrive as
# independent tasks, so without the per-rider lock two of them can both miss the
# channel and each create one.
_rider_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
# Channels this process just created, by rider id, with their creation time. The
# guild cache only learns about a new channel from the gateway, which can lag
# behind create_text_channel returning.
_recently_created_channels: dict[int, tuple[discord.TextChannel, float]] = {}


class RideRequestService:
    """Business logic for handling ride request channel creation."""

    def __init__(self, bot):
        """
        Initialize the service with a bot instance.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot

    async def handle_new_rider_reaction(
        self,
        user: discord.Member,
        guild: discord.Guild,
    ) -> bool:
        """
        Prompt an unregistered rider to register, in their own private channel.

        The channel is created the first time and reused afterwards: reacting again
        re-posts the registration prompt rather than doing nothing, so riders whose
        channel predates the Register button still get one.

        Args:
            user: The user who reacted to the ride announcement.
            guild: The Discord guild where the reaction occurred.

        Returns:
            True if a registration prompt was posted, False otherwise.
        """
        channel_name = f"{user.name.lower()}"
        category = discord.utils.get(guild.categories, id=int(CategoryIds.NEW_RIDES))

        if not category:
            logger.info(f"Category with ID {CategoryIds.NEW_RIDES} not found.")
            return False

        async with _rider_locks[user.id]:
            return await self._prompt_in_rider_channel(user, guild, category, channel_name)

    async def _prompt_in_rider_channel(
        self,
        user: discord.Member,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        channel_name: str,
    ) -> bool:
        """
        Find or create the rider's channel and post the registration prompt there.

        Must run under the rider's lock, so the lookup and the creation are atomic.

        Args:
            user: The user who reacted to the ride announcement.
            guild: The Discord guild where the reaction occurred.
            category: The new-rides category.
            channel_name: The rider's channel name.

        Returns:
            True if a registration prompt was posted, False otherwise.
        """
        # Reuse the rider's existing channel rather than creating a second one.
        existing_channel = discord.utils.get(
            category.channels, name=channel_name
        ) or _get_recently_created_channel(user.id)
        if existing_channel is not None:
            if not isinstance(existing_channel, discord.TextChannel):
                logger.warning(f"Channel {channel_name} exists but is not a text channel.")
                return False
            if await self._latest_message_is_prompt(existing_channel):
                logger.info(
                    f"Registration prompt is already the latest message in {channel_name}; "
                    "skipping re-post."
                )
                return False
            logger.info(f"Channel {channel_name} already exists; re-posting registration prompt.")
            return await self._send_registration_prompt(existing_channel, user)

        # Build permissions
        overwrites = self._build_channel_permissions(guild, user)

        # Create the channel
        try:
            new_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=cast(Any, overwrites),
                reason=f"{user.name} reacted for rides.",
            )
            logger.info(f"Created ride channel: {new_channel}")
            _recently_created_channels[user.id] = (new_channel, time.monotonic())
        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel for {user.name}")
            return False
        except Exception:
            logger.exception(f"Failed to create channel for {user.name}")
            await send_error_to_discord(
                f"**Unexpected Error** creating ride channel for `{user.name}`"
            )
            return False

        await self._send_registration_prompt(new_channel, user)

        # The channel exists either way, so a failed prompt doesn't fail the flow.
        return True

    async def _latest_message_is_prompt(self, channel: discord.TextChannel) -> bool:
        """
        Return whether the channel's newest message is already a registration prompt.

        This keeps repeated reactions from stacking identical prompts, without
        storing any state. It fails open: if the history can't be read, the caller
        posts anyway, since prompting is the point.

        Args:
            channel: The rider's private new-rides channel.

        Returns:
            True if the newest message is one of our prompts.
        """
        bot_user = getattr(self.bot, "user", None)
        try:
            async for message in channel.history(limit=1):
                if bot_user is not None and message.author.id != bot_user.id:
                    return False
                return any(
                    getattr(child, "custom_id", None) in PICKUP_INFO_BUTTON_CUSTOM_IDS
                    for row in message.components
                    for child in getattr(row, "children", ())
                )
        except Exception:
            logger.exception(f"Couldn't read history in {channel.name}; posting prompt anyway")
        return False

    async def _send_registration_prompt(
        self, channel: discord.TextChannel, user: discord.Member
    ) -> bool:
        """
        Post the welcome text and the pickup-info buttons into a rider's channel.

        Args:
            channel: The rider's private new-rides channel.
            user: The rider to greet.

        Returns:
            True if the prompt was posted.
        """
        try:
            await channel.send(
                f"Hi {user.mention}! Thanks for signing up for rides in <#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}>. "
                "Glad you're coming! We just need to know where to pick you up, so tap the "
                "button below that matches where you live. (You only need to do this once)",
                allowed_mentions=discord.AllowedMentions(users=True),
                view=PickupInfoView(),
            )
        except Exception:
            logger.exception(f"Failed to send registration prompt to {channel.name}")
            await send_error_to_discord(
                f"**Unexpected Error** sending registration prompt to `{channel.name}`"
            )
            return False

        return True

    def _build_channel_permissions(
        self, guild: discord.Guild, user: discord.Member
    ) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
        """
        Build permission overwrites for a new ride channel.

        Args:
            guild: The Discord guild.
            user: The user the channel is for.

        Returns:
            Dictionary of permission overwrites.
        """
        ride_coordinator_role = guild.get_role(RoleIds.RIDE_COORDINATOR)

        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
            ),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
        }

        # Add ride coordinator role
        if ride_coordinator_role:
            overwrites[ride_coordinator_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            )

        # Add all admin roles
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                )

        return overwrites


def _get_recently_created_channel(user_id: int) -> discord.TextChannel | None:
    """
    Return the channel this process created for a rider moments ago, if any.

    Args:
        user_id: The rider's Discord user id.

    Returns:
        The channel, or None if none was created within the memory window.
    """
    entry = _recently_created_channels.get(user_id)
    if entry is None:
        return None
    channel, created_at = entry
    if time.monotonic() - created_at > NEW_RIDER_CHANNEL_MEMORY_SECONDS:
        del _recently_created_channels[user_id]
        return None
    return channel
