"""Service for fetching and caching Discord reactions."""

import logging
from collections import defaultdict

from bot.core.database import AsyncSessionLocal
from bot.core.enums import (
    AskRidesMessage,
    CacheNamespace,
    ChannelIds,
    Emoji,
    RideOption,
    RoleIds,
)
from bot.repositories.locations_repository import LocationsRepository
from bot.utils.cache import _get_reaction_cache_ttl, alru_cache
from bot.utils.parsing import get_message_and_embed_content
from bot.utils.time_helpers import get_last_sunday

logger = logging.getLogger(__name__)


class ReactionService:
    """Handles fetching and caching Discord message reactions."""

    def __init__(self, bot):
        """Initialize the ReactionService."""
        self.bot = bot

    @alru_cache(
        ttl=_get_reaction_cache_ttl, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_REACTIONS
    )
    async def get_usernames_who_reacted(self, channel_id: int, message_id: int, option=None):
        """
        Retrieves a set of usernames who reacted to a message.

        Args:
            channel_id: The channel ID.
            message_id: The message ID.
            option: Optional filtering based on reaction emoji.

        Returns:
            A set of usernames who reacted.
        """
        usernames_reacted = set()
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        for reaction in message.reactions:
            if (
                option
                and option == RideOption.SUNDAY_DROPOFF_BACK
                and (str(reaction.emoji) in [Emoji.LUNCH, Emoji.SOMETHING_ELSE])
            ):
                continue
            if (
                option
                and option == RideOption.SUNDAY_DROPOFF_LUNCH
                and (str(reaction.emoji) in [Emoji.NO_LUNCH, Emoji.SOMETHING_ELSE])
            ):
                continue
            async for user in reaction.users():
                if not user.bot:
                    usernames_reacted.add(user.name)
        return usernames_reacted

    @alru_cache(
        ttl=_get_reaction_cache_ttl, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_REACTIONS
    )
    async def get_ask_rides_reactions(self, event: AskRidesMessage):
        """
        Retrieves reaction breakdown for an ask-rides message.

        Args:
            event: The AskRidesMessage type to look up.

        Returns:
            Dictionary with reactions mapping emojis to lists of usernames,
            username_to_name mapping. None if message not found.
        """
        import discord

        channel_id = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
        message_id = await self.find_correct_message(event, channel_id)
        if not message_id:
            return None

        channel = self.bot.get_channel(channel_id)
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            logger.warning(
                f"Message {message_id} for {event} not found (deleted?); clearing stale cache"
            )
            await self.find_correct_message.cache_set(event, channel_id, result=None)
            return None

        reactions_by_emoji = defaultdict(list)
        all_usernames = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    username = user.name
                    reactions_by_emoji[str(reaction.emoji)].append(username)
                    all_usernames.add(username)

        async with AsyncSessionLocal() as session:
            username_to_name = await LocationsRepository.get_names_for_usernames(
                session, all_usernames
            )

        return {
            "reactions": dict(reactions_by_emoji),
            "username_to_name": username_to_name,
        }

    @alru_cache(
        ttl=_get_reaction_cache_ttl,
        ignore_self=True,
        namespace=CacheNamespace.ASK_DRIVERS_REACTIONS,
    )
    async def get_driver_reactions(self, event: AskRidesMessage):
        """
        Retrieves reaction breakdown for a driver message.

        Args:
            event: AskRidesMessage.FRIDAY_FELLOWSHIP or AskRidesMessage.SUNDAY_SERVICE

        Returns:
            Dictionary with reactions mapping emojis to lists of usernames,
            and username_to_name mapping for display purposes.
        """
        logger.debug(f"get_driver_reactions: event={event}")
        if event not in (AskRidesMessage.FRIDAY_FELLOWSHIP, AskRidesMessage.SUNDAY_SERVICE):
            raise ValueError(f"Invalid event for driver reactions: {event}")

        import discord

        channel_id = ChannelIds.SERVING__DRIVER_CHAT_WOOOOO

        logger.debug("get_driver_reactions: looking up driver message")
        message_id = await self.find_driver_message(event, channel_id)
        if not message_id:
            return None

        channel = self.bot.get_channel(channel_id)
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            logger.warning(
                f"Message {message_id} for {event} not found (deleted?); clearing stale cache"
            )
            await self.find_driver_message.cache_set(event, channel_id, result=None)
            return None

        reactions_by_emoji = defaultdict(list)
        all_usernames = set()
        for reaction in message.reactions:
            async for user in reaction.users():
                if not user.bot:
                    username = user.name
                    reactions_by_emoji[str(reaction.emoji)].append(username)
                    all_usernames.add(username)

        async with AsyncSessionLocal() as session:
            username_to_name = await LocationsRepository.get_names_for_usernames(
                session, all_usernames
            )

        return {
            "reactions": dict(reactions_by_emoji),
            "username_to_name": username_to_name,
        }

    @alru_cache(ttl=864000, ignore_self=True, namespace=CacheNamespace.ASK_RIDES_MESSAGE_ID)
    async def find_correct_message(self, ask_rides_message: AskRidesMessage, channel_id):
        """
        Finds the most recent message matching the criteria.

        Args:
            ask_rides_message: The message content to search for.
            channel_id: The channel ID to search in.

        Returns:
            The message ID if found, otherwise None.
        """
        results = await self._find_all_messages(channel_id)
        return results.get(ask_rides_message)

    async def _find_all_messages(self, channel_id) -> dict[AskRidesMessage, int | None]:
        """
        Scans channel history once and finds all AskRidesMessage matches.

        Args:
            channel_id: The channel ID to search in.

        Returns:
            Dictionary mapping each AskRidesMessage to its message ID (or None).
        """
        last_sunday = get_last_sunday()
        channel = self.bot.get_channel(channel_id)
        results: dict[AskRidesMessage, int | None] = dict.fromkeys(AskRidesMessage)

        if not channel:
            return results

        most_recent: dict[AskRidesMessage, object] = {}
        async for message in channel.history(after=last_sunday):
            combined_text = get_message_and_embed_content(message, message_content=False).lower()
            for msg_type in AskRidesMessage:
                if msg_type.lower() in combined_text:
                    most_recent[msg_type] = message

        for msg_type, message in most_recent.items():
            results[msg_type] = message.id

        for msg_type, msg_id in results.items():
            await self.find_correct_message.cache_set(msg_type, channel_id, result=msg_id)

        return results

    @alru_cache(ttl=864000, ignore_self=True, namespace=CacheNamespace.ASK_DRIVERS_MESSAGE_ID)
    async def find_driver_message(
        self, event: AskRidesMessage, channel_id: int = ChannelIds.SERVING__DRIVER_CHAT_WOOOOO
    ):
        """
        Finds the most recent driver message matching the keyword.

        Args:
            event: The event to search for (e.g., "Friday", "Sunday").
            channel_id: The channel ID to search in.

        Returns:
            The message ID if found, otherwise None.
        """
        logger.debug("find_driver_message: looking up results")
        results = await self._find_all_driver_messages(channel_id)
        logger.debug("find_driver_message: got results")
        return results.get(event)

    async def _find_all_driver_messages(
        self,
        channel_id: int = ChannelIds.SERVING__DRIVER_CHAT_WOOOOO,
    ) -> dict[AskRidesMessage, int | None]:
        """
        Scans driver channel history once and finds all driver message matches.

        Args:
            channel_id: The channel ID to search in.

        Returns:
            Dictionary mapping each AskRidesMessage to its driver message ID (or None).
        """
        logger.debug("_find_all_driver_messages: starting scan")
        driver_keywords: dict[AskRidesMessage, list[str]] = {
            AskRidesMessage.FRIDAY_FELLOWSHIP: ["friday", "felly", "fellowship"],
            AskRidesMessage.SUNDAY_SERVICE: ["sunday", "service"],
            AskRidesMessage.SUNDAY_CLASS: ["sunday", "class"],
        }

        last_sunday = get_last_sunday()
        channel = self.bot.get_channel(channel_id)
        results: dict[AskRidesMessage, int | None] = dict.fromkeys(driver_keywords)

        if not channel:
            return results

        driver_role_mention = f"<@&{RoleIds.DRIVER}>"

        most_recent: dict[AskRidesMessage, object] = {}
        async for message in channel.history(after=last_sunday):
            if driver_role_mention not in message.content:
                continue
            combined_text = get_message_and_embed_content(message).lower()
            logger.debug(f"combined_text: {combined_text}")
            for event, keywords in driver_keywords.items():
                if any(kw in combined_text for kw in keywords):
                    most_recent[event] = message

        for event, message in most_recent.items():
            results[event] = message.id

        for event, msg_id in results.items():
            await self.find_driver_message.cache_set(event, channel_id, result=msg_id)

        return results
