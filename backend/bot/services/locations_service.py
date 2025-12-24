"""Service for location-related operations."""

import csv
import gc
import io
import os
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal

import discord
import requests
from dotenv import load_dotenv

from bot.core.database import AsyncSessionLocal
from bot.core.enums import AskRidesMessage, CanBeDriver, ChannelIds, ClassYear
from bot.core.logger import logger
from bot.core.models import Locations as LocationsModel
from bot.repositories.locations_repository import LocationsRepository
from bot.utils.custom_exceptions import NoMatchingMessageFoundError, NotAllowedInChannelError
from bot.utils.parsing import get_message_and_embed_content

load_dotenv()

LSCC_PPL_CSV_URL = os.getenv("LSCC_PPL_CSV_URL")

RideOptionsSchema = Literal[
    "Sunday pickup", "Sunday dropoff back", "Sunday dropoff lunch", "Friday"
]

SCHOLARS_LOCATIONS = [
    "revelle",
    "muir",
    "sixth",
    "marshall",
    "erc",
    "seventh",
    "new marshall",
    "eighth",
]


class LocationsService:
    """Service for handling location data and synchronization."""

    def __init__(self, bot):
        self.bot = bot
        self.repo = LocationsRepository()

    async def sync_locations(self):
        """Syncs the Google Sheet with database table `locations`.

        Raises:
            Exception: If LSCC_PPL_CSV_URL is not set or data retrieval fails.
        """
        logger.info("Syncing locations...")
        if not LSCC_PPL_CSV_URL:
            raise Exception("LSCC_PPL_CSV_URL environment variable not set.")

        response = requests.get(LSCC_PPL_CSV_URL)

        if response.status_code != 200:
            raise Exception("Failed to retrieve data.")

        csv_data = response.content.decode("utf-8")
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)

        locations_to_add = []
        for row in reader:
            name = self._get_info(row, "Name")
            if not name:
                # The 'name' column is not nullable, so we skip rows without a valid name.
                continue

            locations_to_add.append(
                LocationsModel(
                    name=name.title(),
                    discord_username=self._get_info(row, "Discord Username"),
                    year=self._get_info(row, "Year", self._verify_year),
                    location=self._get_info(row, "Location"),
                    driver=self._get_info(row, "Driver", self._verify_driver),
                )
            )

        async with AsyncSessionLocal() as session:
            await self.repo.sync_locations(session, locations_to_add)

        reader = None
        locations_to_add = None
        gc.collect()
        logger.info("Finished syncing locations csv with table.")

    def _verify_year(self, year: str) -> bool:
        """Verifies if the year is valid.

        Args:
            year: The year string to verify.

        Returns:
            True if valid, False otherwise.
        """
        return year in [year.value for year in ClassYear]

    def _verify_driver(self, driver: str) -> bool:
        """Verifies if the driver status is valid.

        Args:
            driver: The driver status string.

        Returns:
            True if valid, False otherwise.
        """
        return driver in [driver.value for driver in CanBeDriver]

    def _get_info(self, data: dict, key: str, verify_schema: Callable | None = None) -> str | None:
        """Extracts and verifies information from a dictionary.

        Args:
            data: The dictionary containing data.
            key: The key to extract.
            verify_schema: Optional callback to verify the extracted value.

        Returns:
            The extracted string if valid, otherwise None.
        """
        value = data.get(key)
        # Ensure value is a string and not just whitespace
        if not isinstance(value, str) or not value.strip():
            return None

        info = value.strip().lower()
        if verify_schema is not None and not verify_schema(info):
            return None
        return info

    async def get_location(
        self, name: str, discord_only: bool = False
    ) -> list[tuple[str, str]] | None:
        """Retrieves location information for a given name.

        Args:
            name: The name to search for.
            discord_only: If True, only search for Discord username matches.

        Returns:
            A list of tuples containing (name, location) if found, otherwise None.
        """
        async with AsyncSessionLocal() as session:
            possible_people = (
                await self.repo.get_location_check_discord(session, name)
                if discord_only
                else await self.repo.get_location_check_name_and_discord(session, name)
            )
        if possible_people:
            return possible_people

        logger.info("Cache miss in get_location. Triggering sync and retrying.")
        await self.sync_locations()

        async with AsyncSessionLocal() as session:
            possible_people = (
                await self.repo.get_location_check_discord(session, name)
                if discord_only
                else await self.repo.get_location_check_name_and_discord(session, name)
            )
        return possible_people if possible_people else None

    async def get_name_location_no_sync(self, discord_username: str) -> tuple[str, str] | None:
        """Retrieves name and location for a Discord username without syncing.

        Args:
            discord_username: The Discord username to search for.

        Returns:
            A tuple containing (name, location) if found, otherwise None.
        """
        async with AsyncSessionLocal() as session:
            person = await self.repo.get_name_location(session, discord_username)
        return person

    async def pickup_location(self, name: str) -> str:
        """Formats pickup location information for a given name.

        Args:
            name: The name to search for.

        Returns:
            A formatted string with name and location.
        """
        possible_people = await self.get_location(name)
        if not possible_people:
            return "No people found."
        return "\n".join(f"{n}: {loc}" for n, loc in possible_people)

    async def list_locations_wrapper(
        self,
        interaction,
        day=None,
        message_id: int | None = None,
        channel_id: int = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        """Wrapper for listing locations, handling interaction responses and errors.

        Args:
            interaction: The Discord interaction.
            day: The day to list locations for.
            message_id: The message ID to check reactions on.
            channel_id: The channel ID where the message is located.
            option: Additional filtering options.
        """
        try:
            args = await self.list_locations(day, message_id, channel_id, option)
            embed = self._build_embed(*args, option=option)
            if day and option and "dropoff" in option.lower():
                non_discord = await self.repo.get_non_discord_pickups(day)
                if non_discord:
                    non_discord_locations_people = defaultdict(list)
                    for pickup in non_discord:
                        non_discord_locations_people[pickup.location].append((pickup.name, None))
                    await interaction.response.send_message(
                        embeds=[
                            embed,
                            self._build_embed(
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
        except Exception as e:
            logger.exception("An error occurred: ")
            await interaction.response.send_message(f"Unknown error: {e}")

    async def list_locations(
        self,
        day=None,
        message_id: int | None = None,
        channel_id: int = ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS,
        option=None,
    ):
        """Lists locations based on reactions to a message.

        Args:
            day: The day to list locations for.
            message_id: The message ID to check reactions on.
            channel_id: The channel ID where the message is located.
            option: Additional filtering options.

        Returns:
            A tuple containing (locations_people, usernames_reacted, location_found).
        """
        logger.info(f"Calling list_locations with day={day}, message_id={message_id}, channel_id={channel_id}, option={option}")
        if day:
            if day.lower() == "sunday":
                ask_rides_message = AskRidesMessage.SUNDAY_SERVICE
            elif day.lower() == "friday":
                ask_rides_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            else:
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
            (day and day.lower() == "sunday")
            or ("service" in tmp_content and "sunday" in tmp_content)
        ) and (
            class_message_id := await self._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, channel_id
            )
        ) is not None:
            usernames_reacted -= await self._get_usernames_who_reacted(channel_id, class_message_id)

        locations_people, location_found = await self._sort_locations(usernames_reacted)

        if day and (option is None or "dropoff" not in option.lower()):
            pickups = await self.repo.get_non_discord_pickups(day)
            for pickup in pickups:
                locations_people[pickup.location].append((pickup.name, None))

        return locations_people, usernames_reacted, location_found

    def _get_last_sunday(self):
        """Calculates the date of the last Sunday.

        Returns:
            The datetime object for the last Sunday.
        """
        now = datetime.now()
        days_to_subtract = (now.weekday() + 1) % 7
        if days_to_subtract == 0:
            days_to_subtract = 7
        return now - timedelta(days=days_to_subtract)

    async def _find_correct_message(self, ask_rides_message: AskRidesMessage, channel_id):
        """Finds the most recent message matching the criteria.

        Args:
            ask_rides_message: The message content to search for.
            channel_id: The channel ID to search in.

        Returns:
            The message ID if found, otherwise None.
        """
        last_sunday = self._get_last_sunday()
        channel = self.bot.get_channel(channel_id)
        most_recent_message = None
        if not channel:
            return None
        async for message in channel.history(after=last_sunday):
            combined_text = get_message_and_embed_content(message, message_content=False)
            if ask_rides_message.lower() in combined_text.lower():
                most_recent_message = message
        return most_recent_message.id if most_recent_message else None

    async def _get_usernames_who_reacted(self, channel_id: int, message_id: int, option=None):
        """Retrieves a set of usernames who reacted to a message.

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
            if option and option == "Sunday dropoff back" and (str(reaction.emoji) in ["🍔", "✳️"]):
                continue
            if option and option == "Sunday dropoff lunch" and (str(reaction.emoji) in ["🏠", "✳️"]):
                continue
            async for user in reaction.users():
                if not user.bot:
                    usernames_reacted.add(user)
        return usernames_reacted

    async def _sort_locations(self, usernames_reacted):
        """Sorts users into locations based on their database records.

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

    def group_locations_by_housing(self, locations_people, usernames_reacted, location_found):
        """Groups locations into housing categories.

        Args:
            locations_people: Dictionary mapping locations to people.
            usernames_reacted: Set of all usernames who reacted.
            location_found: Set of usernames whose location was found.

        Returns:
            A dictionary with housing groups and unknown users:
            {
                "groups": {
                    "Scholars": {"count": int, "locations": {location: [people]}, "emoji": str},
                    ...
                },
                "unknown_users": [str]
            }
        """
        housing_groups = {
            "Scholars": {"count": 0, "locations": {}, "filter": SCHOLARS_LOCATIONS, "emoji": "🏫"},
            "Warren + Pepper Canyon": {
                "count": 0,
                "locations": {},
                "filter": [
                    "warren",
                    "pcyn",
                    "pce",
                    "pcw",
                    "pepper canyon east",
                    "pepper canyon west",
                ],
                "emoji": "🏠",
            },
            "Rita": {"count": 0, "locations": {}, "filter": ["rita"], "emoji": "🏡"},
            "Off Campus": {"count": 0, "locations": {}, "filter": [], "emoji": "🌍"},
        }

        # Group locations into housing categories
        for location, people_username_list in locations_people.items():
            # Don't flatten to just names yet, keep the full tuple
            people = people_username_list
            matched = False
            
            for group_name, group_data in housing_groups.items():
                if any(keyword in location.lower() for keyword in group_data["filter"]):
                    group_data["count"] += len(people)
                    group_data["locations"][location] = people
                    matched = True
                    break
            
            if not matched:
                housing_groups["Off Campus"]["count"] += len(people)
                housing_groups["Off Campus"]["locations"][location] = people

        # Get unknown users
        unknown_location = set(usernames_reacted) - location_found
        unknown_users = [str(user) for user in unknown_location] if unknown_location else []

        return {
            "groups": housing_groups,
            "unknown_users": unknown_users
        }

    def _build_embed(
        self, locations_people, usernames_reacted, location_found, option=None, custom_title=None
    ):
        """Builds a Discord embed displaying location breakdowns.

        Args:
            locations_people: Dictionary mapping locations to people.
            usernames_reacted: Set of all usernames who reacted.
            location_found: Set of usernames whose location was found.
            option: Optional filter option string.
            custom_title: Optional custom title for the embed.

        Returns:
            A Discord Embed object.
        """
        title = "Housing Breakdown"
        if option:
            title += f" ({option})"
        embed = discord.Embed(
            title=title if custom_title is None else custom_title, color=discord.Color.blue()
        )

        # Use the helper function to group locations
        grouped_data = self.group_locations_by_housing(locations_people, usernames_reacted, location_found)

        # Build embed fields from grouped data
        for group_name, group_data in grouped_data["groups"].items():
            if group_data["count"] > 0:
                # Format the people string for this group
                people_str = ""
                for location, people in group_data["locations"].items():
                    # Extract just the names for the Discord embed
                    people_names = [p[0] for p in people]
                    people_str += f"**({len(people)}) {location}:** {', '.join(people_names)}\n"
                
                embed.add_field(
                    name=f"{group_data['emoji']} [{group_data['count']}] {group_name}",
                    value=people_str,
                    inline=False,
                )

        # Add unknown users if any
        if grouped_data["unknown_users"]:
            embed.add_field(
                name=f"❓ [{len(grouped_data['unknown_users'])}] Unknown Location",
                value=", ".join(grouped_data["unknown_users"])
                + "\n(Make sure their Discord username is correct in the sheet!)",
                inline=False,
            )
        
        return embed
