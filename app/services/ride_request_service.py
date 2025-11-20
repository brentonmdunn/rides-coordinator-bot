import discord

from app.core.enums import CategoryIds, ChannelIds, RoleIds
from app.core.logger import logger


class RideRequestService:
    """Business logic for handling ride request channel creation."""

    def __init__(self, bot):
        """Initialize the service with a bot instance.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot

    async def handle_new_rider_reaction(
        self,
        user: discord.Member,
        guild: discord.Guild,
    ) -> bool:
        """Handle a new rider reaction by creating a private channel.

        When a user without a registered location reacts to a ride announcement,
        this creates a private channel where ride coordinators can collect their
        location information.

        Args:
            user: The user who reacted to the ride announcement.
            guild: The Discord guild where the reaction occurred.

        Returns:
            True if channel was created successfully, False otherwise.
        """
        channel_name = f"{user.name.lower()}"
        category = discord.utils.get(guild.categories, id=int(CategoryIds.NEW_RIDES))

        if not category:
            logger.info(f"Category with ID {CategoryIds.NEW_RIDES} not found.")
            return False

        # Check if channel already exists
        existing_channel = discord.utils.get(category.channels, name=channel_name)
        if existing_channel:
            logger.info(f"Channel {channel_name} already exists.")
            return False

        # Build permissions
        overwrites = self._build_channel_permissions(guild, user)

        # Create the channel
        try:
            new_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"{user.name} reacted for rides.",
            )
            logger.info(f"Created ride channel: {new_channel}")
        except discord.Forbidden:
            logger.error(f"Missing permissions to create channel for {user.name}")
            return False
        except Exception as e:
            logger.error(f"Failed to create channel for {user.name}: {e}")
            return False

        # Send welcome message
        try:
            await new_channel.send(
                f"Hi {user.mention}! Thanks for reacting for rides in <#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}>. "
                "We don't yet know where to pick you up. "
                "If you live **on campus**, please share the college or neighborhood where you live (e.g., Sixth, Pepper Canyon West, Rita). "
                "If you live **off campus**, please share your apartment complex or address. "
                "One of our ride coordinators will check in with you shortly!",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except Exception as e:
            logger.error(f"Failed to send welcome message to {new_channel.name}: {e}")
            # Channel was created, so still return True

        return True

    def _build_channel_permissions(
        self, guild: discord.Guild, user: discord.Member
    ) -> dict[discord.Role | discord.Member, discord.PermissionOverwrite]:
        """Build permission overwrites for a new ride channel.

        Args:
            guild: The Discord guild.
            user: The user the channel is for.

        Returns:
            Dictionary of permission overwrites.
        """
        ride_coordinator_role = guild.get_role(RoleIds.RIDE_COORDINATOR)

        overwrites = {
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
