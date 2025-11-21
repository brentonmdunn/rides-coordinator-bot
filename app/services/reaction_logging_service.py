"""Service for logging reaction events."""
import discord

from app.core.enums import ChannelIds
from app.core.logger import logger
from app.core.reaction_enums import ReactionAction
from app.utils.format_message import message_link
from app.utils.parsing import get_message_and_embed_content


class ReactionLoggingService:
    """Business logic for logging reaction events."""

    def __init__(self, bot):
        """Initialize the service with a bot instance.

        Args:
            bot: The Discord bot instance.
        """
        self.bot = bot

    async def log_reaction(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        channel: discord.TextChannel,
        action: ReactionAction,
    ) -> bool:
        """Log a reaction event to the bot logs channel.

        Args:
            user: The user who reacted.
            payload: The raw reaction event payload.
            message: The message that was reacted to.
            channel: The channel where the message was sent.
            action: Whether the reaction was added or removed.

        Returns:
            True if logged successfully, False otherwise.
        """
        log_channel = self.bot.get_channel(ChannelIds.BOT_STUFF__BOT_LOGS)
        if not log_channel or not isinstance(log_channel, discord.TextChannel):
            return False

        log_message = self._format_reaction_log(user, payload, message, channel, action)

        try:
            await log_channel.send(log_message)
            return True
        except discord.Forbidden:
            logger.error(f"Missing permissions to send to channel {log_channel.id}")
            return False
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")
            return False

    async def log_late_ride_reaction(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        action: ReactionAction,
    ) -> bool:
        """Log a late ride reaction to the driver bot spam channel.

        Args:
            user: The user who reacted.
            payload: The raw reaction event payload.
            message: The message that was reacted to.
            action: Whether the reaction was added or removed.

        Returns:
            True if logged successfully, False otherwise.
        """
        log_channel = self.bot.get_channel(ChannelIds.SERVING__DRIVER_BOT_SPAM)
        if not log_channel or not isinstance(log_channel, discord.TextChannel):
            return False

        log_message = self._format_reaction_log_late_rides(user, payload, message, action)

        try:
            await log_channel.send(log_message)
            return True
        except discord.Forbidden:
            logger.error(f"Missing permissions to send to channel {log_channel.id}")
            return False
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")
            return False

    def _format_reaction_log(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        channel: discord.TextChannel,
        action: ReactionAction,
    ) -> str:
        """Formats a reaction log message.

        Args:
            user: The user who reacted.
            payload: The payload of the reaction event.
            message: The message that was reacted to.
            channel: The channel where the message was sent.
            action: The action taken (add or remove).

        Returns:
            The formatted log message.

        Raises:
            ValueError: If the action is not valid.
        """
        if action == ReactionAction.ADD:
            verb = "reacted"
        elif action == ReactionAction.REMOVE:
            verb = "removed their reaction"
        else:
            raise ValueError(f"Invalid action: {action}")

        link = message_link(channel.guild.id, channel.id, message.id)

        # Handle empty message content (e.g., embeds, images)
        content = message.content or "[No Content/Embed]"

        return f"`{user.name}` {verb} {payload.emoji} to message \n```{content}\n```Message link: {link}"  # noqa E501

    def _format_reaction_log_late_rides(
        self,
        user: discord.Member,
        payload: discord.RawReactionActionEvent,
        message: discord.Message,
        action: ReactionAction,
    ) -> str:
        """Format a log message for late ride reactions.

        Creates a human-readable log message indicating which user reacted to which
        event (Friday Fellowship or Sunday Service) during a late time window.

        Args:
            user: The user who reacted.
            payload: The raw reaction event payload containing emoji information.
            message: The message that was reacted to.
            action: Whether the reaction was added or removed.

        Returns:
            A formatted string describing the late ride reaction.

        Raises:
            ValueError: If the action is not ADD or REMOVE.
        """
        if action not in (ReactionAction.ADD, ReactionAction.REMOVE):
            raise ValueError(f"Invalid action: {action}")

        action_verb = "reacted" if action == ReactionAction.ADD else "removed their reaction"

        event_map = {
            "sunday": "Sunday Service",
            "friday": "Friday Fellowship",
        }

        event_name = None
        for keyword, full_name in event_map.items():
            if keyword in get_message_and_embed_content(message).lower():
                event_name = full_name
                break

        if event_name is None:
            return f"`{user.name}` {action_verb} {payload.emoji} to an unknown message."

        return f"`{user.name}` {action_verb} {payload.emoji} to {event_name}"
