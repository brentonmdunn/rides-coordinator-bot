"""Service for handling ride requests."""

import logging
from typing import Any, cast

import discord

from ridebot.views.registration import RegistrationView
from shared.core.enums import CategoryIds, ChannelIds, RoleIds
from shared.core.error_reporter import send_error_to_discord

logger = logging.getLogger(__name__)


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

        # Reuse the rider's existing channel rather than creating a second one.
        existing_channel = discord.utils.get(category.channels, name=channel_name)
        if existing_channel is not None:
            if not isinstance(existing_channel, discord.TextChannel):
                logger.warning(f"Channel {channel_name} exists but is not a text channel.")
                return False
            logger.info(f"Channel {channel_name} already exists; re-posting registration prompt.")
            return await self._send_registration_prompt(existing_channel, user, pin=False)

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
        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel for {user.name}")
            return False
        except Exception:
            logger.exception(f"Failed to create channel for {user.name}")
            await send_error_to_discord(
                f"**Unexpected Error** creating ride channel for `{user.name}`"
            )
            return False

        await self._send_registration_prompt(new_channel, user, pin=True)

        # The channel exists either way, so a failed prompt doesn't fail the flow.
        return True

    async def _send_registration_prompt(
        self, channel: discord.TextChannel, user: discord.Member, *, pin: bool
    ) -> bool:
        """
        Post the welcome text and the Register button into a rider's channel.

        Args:
            channel: The rider's private new-rides channel.
            user: The rider to greet.
            pin: Whether to pin the message. Only a freshly created channel pins it;
                re-posts skip pinning so pins don't pile up.

        Returns:
            True if the prompt was posted.
        """
        try:
            message = await channel.send(
                f"Hi {user.mention}! Thanks for reacting for rides in <#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}>. "
                "We don't yet know where to pick you up.\n"
                "If you live **on campus**, tap **Register** below to tell us your name, "
                "year, and where you live.\n"
                "If you live **off campus**, please share your apartment complex or address "
                "here and a ride coordinator will add you.",
                allowed_mentions=discord.AllowedMentions(users=True),
                view=RegistrationView(),
            )
        except Exception:
            logger.exception(f"Failed to send registration prompt to {channel.name}")
            await send_error_to_discord(
                f"**Unexpected Error** sending registration prompt to `{channel.name}`"
            )
            return False

        if pin:
            try:
                await message.pin()
            except (discord.Forbidden, discord.HTTPException):
                logger.warning(f"Failed to pin welcome message in {channel.name}")

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
