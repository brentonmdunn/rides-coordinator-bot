from enum import StrEnum

import discord
from discord.ext import commands

from app.cogs.locations import Locations
from app.core.enums import CategoryIds, ChannelIds, DaysOfWeek, FeatureFlagNames, RoleIds
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled
from app.utils.lookups import get_location
from app.utils.time_helpers import is_during_target_window


class ReactionAction(StrEnum):
    ADD = "add"
    REMOVE = "remove"


class Reactions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.locations_cog: Locations | None = None

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

        if user:
            if payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS and (
                ("friday" in message.content.lower() and is_during_target_window(DaysOfWeek.FRIDAY))
                or (
                    "sunday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.SUNDAY)
                )
                or (
                    "wednesday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.WEDNESDAY)
                )
            ):
                log_channel = self.bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM)
                if log_channel:
                    await log_channel.send(
                        f"{user.name} reacted {payload.emoji} to message "
                        f"'{discord.utils.escape_mentions(message.content)}' "
                        f"in #{channel.name}",
                    )
                await log_channel.send(
                    _format_reaction_log(user, payload, message, channel, ReactionAction.ADD)
                )
                return

            await self._log_reactions(user, payload, message, channel, ReactionAction.ADD)

            if (
                (self.locations_cog and (await self.locations_cog._find_correct_message("friday")))
                and user is not None
                and not await get_location(user.name, discord_only=True)
            ):
                await self.new_rides_helper(user, guild)

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

        if (
            user
            and payload.channel_id == ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
            and (
                ("friday" in message.content.lower() and is_during_target_window(DaysOfWeek.FRIDAY))
                or (
                    "sunday" in message.content.lower()
                    and is_during_target_window(DaysOfWeek.SUNDAY)
                )
            )
        ):
            log_channel = self.bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM)
            if log_channel:
                await log_channel.send(
                    _format_reaction_log(user, payload, message, channel, ReactionAction.REMOVE)
                )
            return

        await self._log_reactions(user, payload, message, channel, ReactionAction.REMOVE)

    @feature_flag_enabled(FeatureFlagNames.LOG_REACTIONS, enable_logs=False)
    async def _log_reactions(self, user, payload, message, channel, action: ReactionAction):
        log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS)
        if log_channel:
            await log_channel.send(_format_reaction_log(user, payload, message, channel, action))

    @feature_flag_enabled(FeatureFlagNames.NEW_RIDES_MSG)
    async def new_rides_helper(self, user, guild):
        channel_name = f"{user.name.lower()}-test"
        category = discord.utils.get(guild.categories, id=CategoryIds.NEW_RIDES)

        if not category:
            logger.info(f"Category with ID {CategoryIds.NEW_RIDES} not found.")
            return

        existing_channel = discord.utils.get(
            category.channels,
            name=channel_name,
        )
        if existing_channel:
            logger.info(f"Channel {channel_name} already exists.")
            return

        # Permissions

        role = guild.get_role(RoleIds.RIDE_COORDINATOR)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
            ),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
            role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
        }

        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                )

        new_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"{user.name} reacted for rides.",
        )

        await new_channel.send(
            f"Hi {user.mention}! Thanks for reacting in for rides in <#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}>. "  # noqa
            "We don't yet know where to pick you up. "
            "If you live **on campus**, please share the college or neighborhood where you live (e.g., Sixth, Pepper Canyon West, Rita). "  # noqa
            "If you live **off campus**, please share your apartment complex or address. "
            "One of our ride coordinators will check in with you shortly!",
        )


def _format_reaction_log(
    user: discord.Member,
    payload: discord.RawReactionActionEvent,
    message: discord.Message,
    channel: discord.TextChannel,
    action: ReactionAction,
) -> str:
    """Formats a reaction log message.

    Args:
        user (discord.Member): The user who reacted.
        payload (discord.RawReactionActionEvent): The payload of the reaction event.
        message (discord.Message): The message that was reacted to.
        channel (discord.TextChannel): The channel where the message was sent.
        action (ReactionAction): The action taken (add or remove)

    Returns:
        str: The formatted log message.

    Raises:
        ValueError: If the action is not valid.
    """
    if action != ReactionAction.ADD and action != ReactionAction.REMOVE:
        raise ValueError(f"Invalid action: {action}")

    if action == ReactionAction.ADD:
        return (
            f"{user.name} reacted {payload.emoji} to message "
            f"'{discord.utils.escape_mentions(message.content)}' "
            f"in #{channel.name}"
        )
    if action == ReactionAction.REMOVE:
        return (
            f"{user.name} removed their reaction {payload.emoji} from message "
            f"'{discord.utils.escape_mentions(message.content)}' "
            f"in #{channel.name}"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Reactions(bot))
