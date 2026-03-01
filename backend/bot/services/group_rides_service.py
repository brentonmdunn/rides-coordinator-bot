"""Service for group rides logic."""

import asyncio
from datetime import datetime, time, timedelta

import discord

# from langchain_google_genai import ChatGoogleGenerativeAI # Removed
from rapidfuzz import fuzz, process

from bot.api import send_error_to_discord
from bot.core.enums import (
    AskRidesMessage,
    CampusLivingLocations,
    ChannelIds,
    JobName,
    PickupLocations,
)
from bot.core.logger import logger
from bot.core.schemas import (
    Identity,
    # LLMOutputError, # Removed
    # LLMOutputNominal, # Removed
    LocationQuery,
    Passenger,
)
from bot.repositories.group_rides_repository import GroupRidesRepository
from bot.services.llm_service import LLMService
from bot.services.locations_service import LocationsService
from bot.utils.constants import MAP_LINKS

# from bot.utils.genai.prompt import (
#     CUSTOM_INSTRUCTIONS,
#     GROUP_RIDES_PROMPT,
#     GROUP_RIDES_PROMPT_LEGACY,
#     PROMPT_EPILOGUE,
# )
from bot.utils.locations import LOCATIONS_MATRIX, lookup_time
from bot.utils.parsing import get_message_and_embed_content, parse_time

# LLM_MODEL = "gemini-2.5-pro"
# LLM_MODEL = "gemini-2.5-flash"

PICKUP_ADJUSTMENT = 1


living_to_pickup = {
    CampusLivingLocations.SIXTH: PickupLocations.SIXTH,
    CampusLivingLocations.SEVENTH: PickupLocations.SEVENTH,
    CampusLivingLocations.MARSHALL: PickupLocations.MARSHALL,
    CampusLivingLocations.ERC: PickupLocations.ERC,
    CampusLivingLocations.MUIR: PickupLocations.MUIR,
    CampusLivingLocations.EIGHTH: PickupLocations.EIGHTH,
    CampusLivingLocations.REVELLE: PickupLocations.EIGHTH,
    CampusLivingLocations.PCE: PickupLocations.INNOVATION,
    CampusLivingLocations.PCW: PickupLocations.INNOVATION,
    CampusLivingLocations.RITA: PickupLocations.RITA,
    CampusLivingLocations.WARREN: PickupLocations.WARREN_EQL,
}

LocationsPeopleType = dict[str, list[tuple[str, str]]]
PassengersByLocation = dict[PickupLocations, list[Passenger]]


def parse_numbers(s: str) -> list[int]:
    """Parses a string of single-digit numbers and returns a list of integers.

    The input string can have numbers separated by spaces or no spaces at all.
    Each number in the input string must be a single digit from 0 to 9.

    Example input: "4 4 4" or "444"

    Args:
        s (str): The input string.

    Returns:
        list[int]: A list of integers.
    """
    # Remove all spaces from the string
    cleaned_string = s.replace(" ", "")

    return [int(char) for char in cleaned_string]


def find_passenger(locations_people: PassengersByLocation, person: str, location: str) -> Passenger:
    """Finds a passenger object by name and location.

    Args:
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.
        person (str): The name of the person to find.
        location (str): The location key to search in.

    Returns:
        Passenger: The Passenger object if found, otherwise None.
    """
    if location in locations_people:
        for p in locations_people[location]:
            if p.identity.name == person:
                return p
    logger.warning(f"None was returned for {locations_people=} {person=}")
    return None


def count_tuples(data_dict: PassengersByLocation) -> int:
    """Counts the total number of passengers across all locations.

    Args:
        data_dict (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        int: The total count of passengers.
    """
    return sum(len(people_list) for people_list in data_dict.values())


def is_enough_capacity(
    driver_capacity_list: list[int], locations_people: PassengersByLocation
) -> bool:
    """Checks if there is enough driver capacity for all passengers.

    Args:
        driver_capacity_list (list[int]): List of capacities for each driver.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        bool: True if total capacity is greater than or equal to passenger count, False otherwise.
    """
    rider_count = count_tuples(locations_people)
    return sum(driver_capacity_list) >= rider_count


def calculate_pickup_time(
    curr_leave_time: datetime.time, grouped_by_location, location: str, offset: int
) -> datetime.time:
    """Calculates the pickup time based on the previous location and travel time.

    Args:
        curr_leave_time (datetime.time): The leave time from the previous location.
        grouped_by_location (list): List of passenger groups.
        location (str): The current pickup location.
        offset (int): The offset index for the previous location.

    Returns:
        datetime.time: The calculated pickup time.
    """
    time_between = PICKUP_ADJUSTMENT + lookup_time(
        LocationQuery(
            start_location=grouped_by_location[len(grouped_by_location) - offset][
                0
            ].pickup_location,
            end_location=location,
        )
    )
    dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
    new_datetime = dummy_datetime - timedelta(minutes=time_between)
    return new_datetime.time()


def llm_input_drivers(driver_capacity: list[int]) -> str:
    """Formats driver capacity data for LLM input.

    Args:
        driver_capacity (list[int]): List of driver capacities.

    Returns:
        str: A formatted string describing driver capacities.
    """
    return ", ".join(
        f"Driver{i} has capacity {capacity}" for i, capacity in enumerate(driver_capacity)
    )


def llm_input_pickups(locations_people: PassengersByLocation) -> str:
    """Formats pickup location data for LLM input.

    Args:
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.

    Returns:
        str: A formatted string describing pickup locations and passengers.
    """
    return "\n".join(
        f"{location}: {', '.join(person.identity.name for person in locations_people[location])}"
        for location in locations_people
    ) + ("\n" if locations_people else "")


def create_output(
    llm_result: dict[str, list[dict[str, str]]],
    locations_people: PassengersByLocation,
    end_leave_time: datetime.time,
    off_campus: LocationsPeopleType,
) -> list[str]:
    """Creates the final output messages based on the LLM result.

    Args:
        llm_result (dict[str, list[dict[str, str]]]): The result from the LLM.
        locations_people (PassengersByLocation): Dictionary of passengers grouped by location.
        end_leave_time (datetime.time): The target arrival time.
        off_campus (LocationsPeopleType): Dictionary of off-campus passengers.

    Returns:
        list[str]: A list of formatted output strings.
    """
    overall_summary = "==== summary ====\n"

    # Create O(1) lookup map for passengers by name to avoid repeated O(N) searches
    passenger_lookup = {
        passenger.identity.name: passenger
        for passengers in locations_people.values()
        for passenger in passengers
    }
    output_list = []

    for driver_id in llm_result:
        curr_leave_time = end_leave_time
        grouped_by_location: list[list[Passenger]] = []
        curr_location: list[Passenger] = []

        for obj in llm_result[driver_id]:
            person_name = obj["name"]
            location = obj["location"]

            passenger = passenger_lookup.get(person_name)
            if not passenger:
                logger.warning(f"Passenger {person_name} not found in lookup map")
                continue

            # New group or part of same group as prev
            if len(curr_location) == 0 or location == curr_location[-1].pickup_location:
                curr_location.append(passenger)
            # Need to end curr group and create new group
            else:
                grouped_by_location.append(curr_location)
                curr_location: list[Passenger] = []
                curr_location.append(passenger)

        grouped_by_location.append(curr_location)

        drive_formatted = []
        drive_summary = []

        # grouped_by_location is in order by who to pickup first. Need it
        # reversed so can calculate pickup time backwards from goal leave time
        for idx, users_at_location in enumerate(reversed(grouped_by_location)):
            usernames_at_location = [
                p.identity.username if p.identity.username is not None else p.identity.name
                for p in users_at_location
            ]
            names_at_location = [p.identity.name for p in users_at_location]

            pickup_location = users_at_location[0].pickup_location

            if idx != 0:
                curr_leave_time = calculate_pickup_time(
                    curr_leave_time, grouped_by_location, pickup_location, idx
                )

            base_string = (
                f"{' '.join(usernames_at_location)} "
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} "
                f"{pickup_location}"
            )

            # Add google maps link if we have it
            if pickup_location in MAP_LINKS:
                formatted_string = f"{base_string} ([Google Maps]({MAP_LINKS[pickup_location]}))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)
            drive_summary.append(
                f"[{len(names_at_location)}] "
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0').lower()} "
                f"{pickup_location.split()[0]}"
            )

        overall_summary += f"- {' > '.join(reversed(drive_summary))}\n"

        copy_str = f"drive: {', '.join(reversed(drive_formatted))}\n"
        output_list.append(copy_str)
        output_list.append(f"```\n{copy_str}\n```")

    if len(off_campus) != 0:
        overall_summary += "- TODO: off campus\n"
        for key in off_campus:
            overall_summary += f"""  - {key}: {", ".join([f"{person[0]} (`@{person[1]}`)" for person in off_campus[key]])}\n"""  # noqa: E501

    overall_summary += "================="
    output_list.insert(0, overall_summary)
    return output_list


class GroupRidesService:
    """Service for handling group rides logic and LLM interaction."""

    def __init__(self, bot):
        """Initialize the GroupRidesService."""

        self.bot = bot
        # self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)
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
        return living_to_pickup[living_location]

    async def _process_ride_grouping(
        self,
        message_id: int,
        driver_capacity: str,
        channel_id: int,
        legacy_prompt: bool = False,
        custom_prompt: str | None = None,
    ) -> list[str]:
        """
        Core ride grouping logic shared by both Discord and API methods.

        Args:
            message_id: The message ID to fetch pickups from
            driver_capacity: String representing driver capacities
            channel_id: Channel ID where the message is located
            legacy_prompt: Whether to use the legacy prompt
            custom_prompt: Optional custom prompt to use

        Returns:
            List of formatted ride grouping strings

        Raises:
            ValueError: If invalid parameters or insufficient capacity
        """
        # Fetch locations and reactions
        (
            locations_people,
            usernames_reacted,
            location_found,
        ) = await self.locations_service.list_locations(message_id=message_id)

        message = await self.repo.fetch_message(channel_id, message_id)

        if not message:
            raise ValueError("Could not fetch the message content")

        combined_text = get_message_and_embed_content(message)

        # Determine service type and set end leave time
        if "sunday" in combined_text:
            end_leave_time = time(hour=10, minute=10)
            # Filter out people going to class
            class_message_id = await self.locations_service._find_correct_message(
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
            raise ValueError('Message must contain "friday" or "sunday"')

        # Check for unknown locations
        unknown_location = usernames_reacted - location_found
        if unknown_location:
            unknown_names = [str(user) for user in unknown_location]
            raise ValueError(
                f"Unknown location for user(s): {', '.join(unknown_names)}. "
                "Please ensure usernames and locations are on the spreadsheet."
            )

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
                    identity=Identity(name=person[0], username=person[1]),
                    living_location=living_loc_enum,
                    pickup_location=pickup_key,
                )
                for person in locations_people[living_location]
            )

        # Parse driver capacity
        try:
            driver_capacity_list = parse_numbers(driver_capacity)
        except ValueError:
            raise ValueError("driver_capacity must only contain integers") from None

        if not is_enough_capacity(driver_capacity_list, passengers_by_location):
            raise ValueError(
                f"Insufficient driver capacity. "
                f"Riders: {count_tuples(passengers_by_location)}, "
                f"Drivers: {len(driver_capacity_list)}, "
                f"Capacity: {sum(driver_capacity_list)}"
            )

        # Data on driver capacities and pickup locations to send to LLM
        drivers = llm_input_drivers(driver_capacity_list)
        pickups = llm_input_pickups(passengers_by_location)

        try:
            llm_result = await asyncio.to_thread(
                self.llm_service.generate_ride_groups,
                pickups,
                drivers,
                LOCATIONS_MATRIX,
                legacy_prompt,
                custom_prompt,
            )

        except Exception:
            logger.exception("Failed to get a successful LLM response after retries")
            await send_error_to_discord(
                "**Unexpected Error** in `_process_ride_grouping`: LLM failed after retries"
            )
            raise ValueError(
                "Could not process ride grouping request. Please try again later."
            ) from None

        if "error" in {key.lower() for key in llm_result}:
            raise ValueError(f"LLM returned with error: {llm_result}")

        output = create_output(llm_result, passengers_by_location, end_leave_time, off_campus)
        return output

    async def group_rides(
        self,
        interaction: discord.Interaction,
        driver_capacity: str,
        message_id: int | None = None,
        day: str | None = None,
        legacy_prompt: bool = False,
        custom_prompt: str | None = None,
    ):
        """Orchestrates the group rides process.

        Args:
            interaction (discord.Interaction): The Discord interaction.
            driver_capacity (str): String representing driver capacities.
            message_id (int | None, optional): Optional message ID to fetch pickups from.
            day (str | None, optional): Optional day to fetch pickups for.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.
            custom_prompt (str | None, optional): Optional custom prompt to use. Defaults to None.
        """
        await interaction.response.defer()

        if day:
            if day == JobName.FRIDAY:
                ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            elif day == JobName.SUNDAY:
                ask_message = AskRidesMessage.SUNDAY_SERVICE
            else:
                # This shouldn't happen if called correctly
                raise ValueError("Invalid day")

            message_id = await self.locations_service._find_correct_message(
                ask_message, int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)
            )

            if message_id is None:
                await interaction.followup.send("Could not find the rides message.")
                return

        channel_id = int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)

        try:
            output = await self._process_ride_grouping(
                message_id, driver_capacity, channel_id, legacy_prompt, custom_prompt
            )
        except ValueError as e:
            await interaction.followup.send(f"Error: {e!s}")
            return

        await interaction.followup.send(output[0])  # Need one message to respond to previous defer
        # Individual messages allow for easy copy paste
        # Followups reply to the initial response and it looks bad
        for message in output[1:]:
            await interaction.channel.send(message)

    def get_pickup_location_fuzzy(self, input_loc: str) -> PickupLocations | None:
        """Get the fuzzy matched pickup location from an input string.

        Args:
            input_loc (str): The input location string.

        Returns:
            PickupLocations | None: The matched pickup location or None if no match is found.
        """

        choices = {e.value: e for e in PickupLocations}

        # --- PASS 1: High Precision ---
        # Checks for whole words, handles reordering ("bamboo erc" -> "ERC... bamboo")
        result = process.extractOne(
            input_loc,
            choices.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=65,  # Keep this relatively high to avoid bad guesses
        )

        if result:
            return choices[result[0]]

        # --- PASS 2: Fallback (Partial Matching) ---
        # "If a match cannot be found then try to find best match"
        # This handles substrings and typos ("seveneth" -> "Seventh mail room")
        result = process.extractOne(
            input_loc,
            choices.keys(),
            scorer=fuzz.partial_ratio,
            score_cutoff=60,  # Slightly lower cutoff for the fallback
        )

        if result:
            logger.debug(f"{result=}")
            logger.debug(f"Fallback match: '{input_loc}' -> '{result[0]}' (Score: {result[1]})")
            return choices[result[0]]

        return None

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
            # First, try to match by enum key (e.g., "SEVENTH", "MARSHALL")
            try:
                actual_location = PickupLocations[location.upper()]
                locations_list_actual.append(actual_location)
            except KeyError:
                # Fall back to fuzzy matching (e.g., "seventh", "marshall uppers")
                if (actual_location := self.get_pickup_location_fuzzy(location)) is not None:
                    locations_list_actual.append(actual_location)
                else:
                    raise ValueError(f"Invalid location: {location}") from None

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

    async def group_rides_api(
        self,
        message_id: int | None = None,
        day: str | None = None,
        driver_capacity: str = "44444",
        channel_id: int | None = None,
        legacy_prompt: bool = False,
        custom_prompt: str | None = None,
    ) -> dict[str, str | list[str]]:
        """
        Group rides and return structured data (for API use).

        This method is similar to group_rides() but returns data instead of
        sending Discord messages, making it suitable for API endpoints.

        Args:
            message_id: Optional message ID to fetch pickups from
            day: Optional day ("friday" or "sunday") to auto-find message
            driver_capacity: String representing driver capacities
            channel_id: Optional channel ID, defaults to rides announcements
            legacy_prompt: Whether to use the legacy prompt
            custom_prompt: Optional custom prompt to use

        Returns:
            Dictionary with 'summary' and 'groupings' keys

        Raises:
            ValueError: If invalid parameters or insufficient capacity
        """
        if channel_id is None:
            channel_id = int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS)

        # If day is provided, find the corresponding message
        if day:
            if day == JobName.FRIDAY:
                ask_message = AskRidesMessage.FRIDAY_FELLOWSHIP
            elif day == JobName.SUNDAY:
                ask_message = AskRidesMessage.SUNDAY_SERVICE
            else:
                raise ValueError("day must be 'friday' or 'sunday'")

            message_id = await self.locations_service._find_correct_message(ask_message, channel_id)

            if message_id is None:
                raise ValueError(f"Could not find the {day} rides message. It may not exist yet.")

        # Ensure we have a message_id at this point
        if message_id is None:
            raise ValueError("Either message_id or day must be provided")

        output = await self._process_ride_grouping(
            message_id, driver_capacity, channel_id, legacy_prompt, custom_prompt
        )

        # Separate summary and groupings for web app:
        # - First item is the summary
        # - Skip markdown code blocks (items starting with ```)
        # - Return plain formatted groupings
        summary = output[0] if output else ""
        groupings = [
            item
            for item in output[1:]
            if not item.startswith("```")  # Skip markdown code blocks
        ]

        return {"summary": summary, "groupings": groupings}
