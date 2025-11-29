"""Service for group rides logic."""

import asyncio
from datetime import datetime, time, timedelta

import discord

from app.core.enums import (
    AskRidesMessage,
    CampusLivingLocations,
    ChannelIds,
    PickupLocations,
)
from app.core.logger import logger
from app.core.schemas import Identity, LocationQuery, Passenger
from app.repositories.group_rides_repository import GroupRidesRepository
from app.services.llm_service import LLMService
from app.services.locations_service import LocationsService
from app.utils.constants import LIVING_TO_PICKUP, MAP_LINKS
from app.utils.group_rides_helpers import (
    PICKUP_ADJUSTMENT,
    PassengersByLocation,
    count_tuples,
    create_output,
    is_enough_capacity,
    llm_input_drivers,
    llm_input_pickups,
    parse_numbers,
)
from app.utils.locations import LOCATIONS_MATRIX, lookup_time
from app.utils.matching import get_pickup_location_fuzzy
from app.utils.parsing import get_message_and_embed_content, parse_time


class GroupRidesService:
    """Service for handling group rides logic and LLM interaction."""

    def __init__(self, bot):
        self.bot = bot
        self.llm_service = LLMService()
        self.locations_service = LocationsService(bot)
        self.repo = GroupRidesRepository(bot)

    @staticmethod
    def _get_living_location(location: str) -> CampusLivingLocations:
        """Convert location string to CampusLivingLocations enum.

        Args:
            location (str): The location string.

        Returns:
            CampusLivingLocations: The corresponding CampusLivingLocations enum member.
        """
        # Workaround since capitalization is not the same between services
        # Fix is issue #107 https://github.com/brentonmdunn/rides-coordinator-bot/issues/107
        if location.lower() == "erc":
            return CampusLivingLocations.ERC
        return CampusLivingLocations(location.title())

    @staticmethod
    def _get_pickup_location(living_location: CampusLivingLocations) -> PickupLocations:
        """Get pickup location from living location.

        Args:
            living_location (CampusLivingLocations): The living location enum.

        Returns:
            PickupLocations: The corresponding PickupLocations enum member.
        """
        return LIVING_TO_PICKUP[living_location]

    async def group_rides(
        self,
        interaction: discord.Interaction,
        driver_capacity: str,
        message_id: str | None = None,
        day: str | None = None,
        legacy_prompt: bool = False,
    ):
        """Orchestrates the group rides process.

        Args:
            interaction (discord.Interaction): The Discord interaction.
            driver_capacity (str): String representing driver capacities.
            message_id (str | None, optional): Optional message ID to fetch pickups from.
            day (str | None, optional): Optional day to fetch pickups for.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.
        """
        await interaction.response.defer()

        if day:
            if day.lower() == "friday":
                ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            elif day.lower() == "sunday":
                ask_message = AskRidesMessage.SUNDAY_SERVICE
            else:
                # This shouldn't happen if called correctly
                raise ValueError("Invalid day")

            message_id = await self.locations_service.find_correct_message(
                ask_message, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )

            if message_id is None:
                await interaction.followup.send("Could not find the rides message.")
                return

        (
            locations_people,
            usernames_reacted,
            location_found,
        ) = await self.locations_service.list_locations(message_id=message_id)

        channel_id = int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
        message = await self.repo.fetch_message(channel_id, int(message_id))

        if not message:
            # Fallback or error
            await interaction.followup.send("Could not fetch the message content.")
            return

        combined_text = get_message_and_embed_content(message)

        if "sunday" in combined_text:
            end_leave_time = time(hour=10, minute=10)
            class_message_id = await self.locations_service.find_correct_message(
                AskRidesMessage.SUNDAY_CLASS, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )
            if class_message_id is not None:
                (
                    _,
                    class_usernames_reacted,
                    _,
                ) = await self.locations_service.list_locations(message_id=class_message_id)
                usernames_reacted = usernames_reacted - class_usernames_reacted

        elif "friday" in combined_text:
            end_leave_time = time(hour=19, minute=10)
        else:
            # If day was passed, we expect it to match.
            # But if message_id was passed manually, we check content.
            # The original code raises ValueError if neither is found.
            # We can just warn.
            await interaction.followup.send(
                """Error: Please ensure that "friday" or "sunday" is written in message.""",
            )
            return

        unknown_location = usernames_reacted - location_found
        if unknown_location:
            unknown_names = [str(user) for user in unknown_location]
            await interaction.followup.send(
                f"Error: Please ensure that {', '.join(unknown_names)} username(s) and location(s) are on the "  # noqa
                f"[spreadsheet](https://docs.google.com/spreadsheets/d/1uQNUy57ea23PagKhPEmNeQPsP2BUTVvParRrE9CF_Tk/edit?gid=0#gid=0)."
            )
            return

        off_campus = {}
        passengers_by_location: PassengersByLocation = {}

        # Pre-compute valid campus locations for faster lookup
        valid_campus_locations = {location.value.lower() for location in CampusLivingLocations}

        for living_location in locations_people:
            if living_location.lower() not in valid_campus_locations:
                off_campus[living_location] = locations_people[living_location]
                continue

            living_loc_enum = self._get_living_location(living_location)
            pickup_key = self._get_pickup_location(living_loc_enum)

            # Get the existing list or create a new one, then extend it
            passengers_by_location.setdefault(pickup_key, []).extend(
                Passenger(
                    identity=Identity(
                        name=person[0], username=person[1].name if person[1] else None
                    ),
                    living_location=living_loc_enum,
                    pickup_location=pickup_key,
                )
                for person in locations_people[living_location]
            )

        # Parse driver capacity once and reuse
        try:
            driver_capacity_list = parse_numbers(driver_capacity)
        except ValueError:
            await interaction.followup.send(
                "Error: `driver_capacity` must only contain integers.",
                ephemeral=True,
            )
            return

        if not is_enough_capacity(driver_capacity_list, passengers_by_location):
            await interaction.followup.send(
                f"Error: More people need a ride than we have drivers.\n"
                f"Num need rides: {count_tuples(passengers_by_location)}\n"
                f"Num drivers: {len(driver_capacity_list)}\n"
                f"Driver capacity: {sum(driver_capacity_list)}"
            )
            return

        # Data on driver capacities and pickup locations to send to LLM
        drivers = llm_input_drivers(driver_capacity_list)
        pickups = llm_input_pickups(passengers_by_location)

        try:
            llm_result = await asyncio.to_thread(
                self.llm_service.invoke_llm, pickups, drivers, LOCATIONS_MATRIX, legacy_prompt
            )

        except Exception as e:
            logger.error(f"Failed to get a successful LLM response: {e}")
            await interaction.followup.send(
                "Sorry, I couldn't process your request right now. Please try again later.",
                ephemeral=True,
            )
            return

        if "error" in {key.lower() for key in llm_result}:
            await interaction.followup.send(
                f"LLM returned with error: {llm_result}.",
            )

        output = create_output(llm_result, passengers_by_location, end_leave_time, off_campus)
        await interaction.followup.send(output[0])  # Need one message to respond to previous defer
        # Individual messages allow for easy copy paste
        # Followups reply to the initial response and it looks bad
        for message in output[1:]:
            await interaction.channel.send(message)

    def make_route(self, locations: str, leave_time: str) -> str:
        """Makes route based on specified locations.

        Args:
            locations: The locations to make a route for.
            leave_time: The leave time for the route.

        Returns:
            The route as a string.
        """

        curr_leave_time = parse_time(leave_time)
        locations_list = locations.split()
        locations_list_actual = []
        for location in locations_list:
            if (actual_location := get_pickup_location_fuzzy(location)) is not None:
                locations_list_actual.append(actual_location)
            else:
                raise ValueError(f"Invalid location: {location}")

        drive_formatted: list[str] = []
        logger.debug(f"{locations_list_actual=}")

        reversed_locations = list(reversed(locations_list_actual))
        for idx, location in enumerate(reversed_locations):
            if idx != 0:
                time_between = PICKUP_ADJUSTMENT + lookup_time(
                    LocationQuery(start_location=location, end_location=reversed_locations[idx - 1])
                )
                logger.debug(f"{time_between=}")
                dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
                new_datetime = dummy_datetime - timedelta(minutes=time_between)
                curr_leave_time = new_datetime.time()

            logger.debug(f"{curr_leave_time=}")
            logger.debug(f"{location=}")
            base_string = (
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} {location.value}"
            )

            # Add google maps link if we have it
            if location in MAP_LINKS:
                formatted_string = f"{base_string} ([Google Maps]({MAP_LINKS[location]}))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)

        logger.debug(f"{drive_formatted=}")

        return ", ".join(reversed(drive_formatted))
