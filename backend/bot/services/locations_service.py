"""
Service for location-related operations.

Acts as a thin coordinator that delegates to:
- ``CsvSyncService`` for Google Sheets CSV syncing
- ``ReactionService`` for reaction fetching and caching
- ``HousingGroupService`` for location grouping and embed building
"""

import logging
from collections import defaultdict

from bot.core.database import AsyncSessionLocal
from bot.core.enums import (
    DAY_TO_ASK_RIDES_MESSAGE,
    AskRidesMessage,
    ChannelIds,
    JobName,
    RideOption,
)
from bot.core.error_reporter import send_error_to_discord
from bot.repositories.locations_repository import LocationsRepository
from bot.services.csv_sync_service import CsvSyncService
from bot.services.housing_group_service import HousingGroupService
from bot.services.reaction_service import ReactionService
from bot.utils.custom_exceptions import NoMatchingMessageFoundError, NotAllowedInChannelError
from bot.utils.parsing import get_message_and_embed_content

logger = logging.getLogger(__name__)

RideOptionsSchema = RideOption


class LocationsService:
    """Coordinator service for location data and synchronization."""

    def __init__(self, bot):
        """Initialize the LocationsService."""
        self.bot = bot
        self._csv_sync = CsvSyncService()
        self._reactions = ReactionService(bot)
        self._housing = HousingGroupService()

    # ------------------------------------------------------------------
    # Static helpers (no bot required)
    # ------------------------------------------------------------------
    @staticmethod
    async def get_all_discord_usernames() -> list[tuple[str, str]]:
        """Return (discord_username, name) pairs for all rows with a non-null username."""
        async with AsyncSessionLocal() as session:
            return await LocationsRepository.get_all_discord_usernames(session)

    # ------------------------------------------------------------------
    # CSV sync (delegates to CsvSyncService)
    # ------------------------------------------------------------------
    async def sync_locations(self):
        """Syncs the Google Sheet with database table ``locations``."""
        await self._csv_sync.sync_locations()

    # ------------------------------------------------------------------
    # Location lookup
    # ------------------------------------------------------------------
    async def get_location(
        self, name: str, discord_only: bool = False
    ) -> list[tuple[str, str]] | None:
        """
        Retrieves location information for a given name.

        Args:
            name: The name to search for.
            discord_only: If True, only search for Discord username matches.

        Returns:
            A list of tuples containing (name, location) if found, otherwise None.
        """
        async with AsyncSessionLocal() as session:
            possible_people = (
                await LocationsRepository.get_location_check_discord(session, name)
                if discord_only
                else await LocationsRepository.get_location_check_name_and_discord(session, name)
            )
        if possible_people:
            return possible_people

        logger.info("Cache miss in get_location. Triggering sync and retrying.")
        await self.sync_locations()

        async with AsyncSessionLocal() as session:
            possible_people = (
                await LocationsRepository.get_location_check_discord(session, name)
                if discord_only
                else await LocationsRepository.get_location_check_name_and_discord(session, name)
            )
        return possible_people if possible_people else None

    async def get_name_location_no_sync(self, discord_username: str) -> tuple[str, str] | None:
        """
        Retrieves name and location for a Discord username without syncing.

        Args:
            discord_username: The Discord username to search for.

        Returns:
            A tuple containing (name, location) if found, otherwise None.
        """
        async with AsyncSessionLocal() as session:
            person = await LocationsRepository.get_name_location(session, discord_username)
        return person

    async def pickup_location(self, name: str) -> str:
        """
        Formats pickup location information for a given name.

        Args:
            name: The name to search for.

        Returns:
            A formatted string with name and location.
        """
        possible_people = await self.get_location(name)
        if not possible_people:
            return "No people found."
        return "\n".join(f"{n}: {loc}" for n, loc in possible_people)

    # ------------------------------------------------------------------
    # List locations (main coordinator method)
    # ------------------------------------------------------------------
    async def list_locations_wrapper(
        self,
        interaction,
        day=None,
        message_id: int | None = None,
        channel_id: int = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        """
        Wrapper for listing locations, handling interaction responses and errors.

        Args:
            interaction: The Discord interaction.
            day: The day to list locations for.
            message_id: The message ID to check reactions on.
            channel_id: The channel ID where the message is located.
            option: Additional filtering options.
        """
        try:
            logger.info(
                f"list_locations_wrapper: user action - day={day}, "
                f"message_id={message_id}, option={option}"
            )
            args = await self.list_locations(day, message_id, channel_id, option)
            embed = self._housing.build_embed(*args, option=option)
            if day and option and "dropoff" in option.lower():
                async with AsyncSessionLocal() as session:
                    non_discord = await LocationsRepository.get_non_discord_pickups(session, day)
                if non_discord:
                    non_discord_locations_people = defaultdict(list)
                    for pickup in non_discord:
                        non_discord_locations_people[pickup.location].append((pickup.name, None))
                    await interaction.response.send_message(
                        embeds=[
                            embed,
                            self._housing.build_embed(
                                non_discord_locations_people,
                                set(),
                                set(),
                                custom_title="Non-Discord Dropoffs (unknown lunch)",
                            ),
                        ]
                    )
                    return
            await interaction.response.send_message(embed=embed)
        except NotAllowedInChannelError:
            await interaction.response.send_message("Command not allowed in channel.")
        except NoMatchingMessageFoundError:
            await interaction.response.send_message("No matching message found.")
        except Exception:
            logger.exception("An unexpected error occurred in list_locations_wrapper")
            await send_error_to_discord("**Unexpected Error** in `list_locations_wrapper`")
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again later.", ephemeral=True
            )

    async def list_locations(
        self,
        day=None,
        message_id: int | None = None,
        channel_id: int = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        """
        Lists locations based on reactions to a message.

        Args:
            day: The day to list locations for.
            message_id: The message ID to check reactions on.
            channel_id: The channel ID where the message is located.
            option: Additional filtering options.

        Returns:
            A tuple containing (locations_people, usernames_reacted, location_found).
        """
        if day:
            ask_rides_message = DAY_TO_ASK_RIDES_MESSAGE.get(JobName(day))
            if ask_rides_message is None:
                raise ValueError(f"Invalid day: {day}")
            message_id = await self._find_correct_message(ask_rides_message, channel_id)
            if message_id is None:
                raise NoMatchingMessageFoundError()

        usernames_reacted = await self._get_usernames_who_reacted(channel_id, message_id, option)

        tmp_content = ""
        if not day:
            tmp_channel = self.bot.get_channel(int(channel_id))
            tmp_message = await tmp_channel.fetch_message(int(message_id))
            tmp_content = get_message_and_embed_content(tmp_message).lower()

        if (
            (day and day == JobName.SUNDAY)
            or ("service" in tmp_content and "sunday" in tmp_content)
        ) and (
            class_message_id := await self._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, channel_id
            )
        ) is not None:
            # Avoid ``-=`` as it mutates the set in-place, which corrupts the cache.
            usernames_reacted = usernames_reacted - await self._get_usernames_who_reacted(
                channel_id, class_message_id
            )

        locations_people, location_found = await self._sort_locations(usernames_reacted)

        if day and (option is None or "dropoff" not in option.lower()):
            async with AsyncSessionLocal() as session:
                pickups = await LocationsRepository.get_non_discord_pickups(session, day)
            for pickup in pickups:
                locations_people[pickup.location].append((pickup.name, None))

        return locations_people, usernames_reacted, location_found

    # ------------------------------------------------------------------
    # Delegation helpers (maintain backward compatibility)
    # ------------------------------------------------------------------
    async def _find_correct_message(self, ask_rides_message: AskRidesMessage, channel_id):
        """Delegates to ReactionService.find_correct_message."""
        return await self._reactions.find_correct_message(ask_rides_message, channel_id)

    async def _find_all_messages(self, channel_id=None):
        """Delegates to ReactionService._find_all_messages."""
        if channel_id is None:
            channel_id = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS
        return await self._reactions._find_all_messages(channel_id)

    async def _find_driver_message(
        self, event: AskRidesMessage, channel_id: int = ChannelIds.SERVING__DRIVER_CHAT_WOOOOO
    ):
        """Delegates to ReactionService.find_driver_message."""
        return await self._reactions.find_driver_message(event, channel_id)

    async def _find_all_driver_messages(
        self, channel_id: int = ChannelIds.SERVING__DRIVER_CHAT_WOOOOO
    ):
        """Delegates to ReactionService._find_all_driver_messages."""
        return await self._reactions._find_all_driver_messages(channel_id)

    async def _get_usernames_who_reacted(self, channel_id: int, message_id: int, option=None):
        """Delegates to ReactionService.get_usernames_who_reacted."""
        return await self._reactions.get_usernames_who_reacted(channel_id, message_id, option)

    @property
    def get_ask_rides_reactions(self):
        """Exposes the cached ReactionService.get_ask_rides_reactions."""
        return self._reactions.get_ask_rides_reactions

    @property
    def get_driver_reactions(self):
        """Exposes the cached ReactionService.get_driver_reactions."""
        return self._reactions.get_driver_reactions

    def group_locations_by_housing(self, locations_people, usernames_reacted, location_found):
        """Delegates to HousingGroupService.group_locations_by_housing."""
        return self._housing.group_locations_by_housing(
            locations_people, usernames_reacted, location_found
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _sort_locations(self, usernames_reacted):
        """
        Sorts users into locations based on their database records.

        Args:
            usernames_reacted: A set of usernames to sort.

        Returns:
            A tuple containing (locations_people, location_found).
        """
        locations_people = defaultdict(list)
        location_found = set()
        cache_miss = []
        for username in usernames_reacted:
            person = await self.get_name_location_no_sync(username)
            if person is None or person.location is None:
                cache_miss.append(username)
                continue
            locations_people[person.location].append((person.name, username))
            location_found.add(username)
        if cache_miss:
            await self.sync_locations()
            for username in cache_miss:
                person = await self.get_name_location_no_sync(username)
                if person and person.location:
                    locations_people[person.location].append((person.name, username))
                    location_found.add(username)
        return locations_people, location_found
