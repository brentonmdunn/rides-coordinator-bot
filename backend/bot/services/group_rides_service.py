"""Service for group rides logic."""

import asyncio
import logging
from datetime import time

import discord

from bot.core.enums import (
    DAY_TO_ASK_RIDES_MESSAGE,
    AskRidesMessage,
    CampusLivingLocations,
    ChannelIds,
    JobName,
    PickupLocations,
)
from bot.core.error_reporter import send_error_to_discord
from bot.core.schemas import Identity, Passenger
from bot.repositories.group_rides_repository import GroupRidesRepository
from bot.services.llm_service import LLMService
from bot.services.locations_service import LocationsService
from bot.services.ride_grouping import (
    LocationsPeopleType,
    PassengersByLocation,
    count_tuples,
    create_output,
    is_enough_capacity,
    llm_input_drivers,
    llm_input_pickups,
    parse_numbers,
)
from bot.services.route_service import RouteService
from bot.utils.locations import LOCATIONS_MATRIX
from bot.utils.parsing import get_message_and_embed_content

logger = logging.getLogger(__name__)

EVENT_END_LEAVE_TIMES: dict[JobName, time] = {
    JobName.SUNDAY: time(hour=10, minute=10),
    JobName.FRIDAY: time(hour=19, minute=10),
}

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

# Alternative pickup locations per living location. Residents of these
# neighborhoods can be picked up at the primary location from
# ``living_to_pickup`` OR any of the listed alternatives. Empty entries mean
# "no alternatives" (the common case). Currently only Marshall residents
# can flex between Marshall Uppers and Geisel Loop.
living_to_alt_pickups: dict[CampusLivingLocations, list[PickupLocations]] = {
    CampusLivingLocations.MARSHALL: [PickupLocations.GEISEL_LOOP],
}


class GroupRidesService:
    """Service for handling group rides logic and LLM interaction."""

    def __init__(self, bot):
        """Initialize the GroupRidesService."""
        self.bot = bot
        self.llm_service = LLMService()
        self.locations_service = LocationsService(bot)
        self.repo = GroupRidesRepository(bot)
        self._route_service = RouteService()

    @staticmethod
    def _get_living_location(location: str) -> CampusLivingLocations:
        """
        Convert location string to CampusLivingLocations enum.

        Args:
            location (str): The location string.

        Returns:
            CampusLivingLocations: The corresponding CampusLivingLocations enum member.
        """
        if location.lower() == "erc":
            return CampusLivingLocations.ERC
        return CampusLivingLocations(location.title())

    @staticmethod
    def _get_pickup_location(living_location: CampusLivingLocations) -> PickupLocations:
        """
        Get pickup location from living location.

        Args:
            living_location (CampusLivingLocations): The living location enum.

        Returns:
            PickupLocations: The corresponding PickupLocations enum member.
        """
        return living_to_pickup[living_location]

    async def _determine_event_type(self, combined_text: str) -> tuple[JobName, time]:
        """Return the JobName and end leave time inferred from message text."""
        if "sunday" in combined_text:
            return JobName.SUNDAY, EVENT_END_LEAVE_TIMES[JobName.SUNDAY]
        if "friday" in combined_text:
            return JobName.FRIDAY, EVENT_END_LEAVE_TIMES[JobName.FRIDAY]
        raise ValueError('Message must contain "friday" or "sunday"')

    async def _filter_class_attendees(self, usernames_reacted: set, channel_id: int) -> set:
        """Remove Sunday class attendees from the reacted set."""
        class_message_id = await self.locations_service._find_correct_message(
            AskRidesMessage.SUNDAY_CLASS, channel_id
        )
        if class_message_id is None:
            return usernames_reacted
        _, class_usernames_reacted, _ = await self.locations_service.list_locations(
            message_id=class_message_id
        )
        return usernames_reacted - class_usernames_reacted

    def _split_on_off_campus(
        self, locations_people: LocationsPeopleType
    ) -> tuple[PassengersByLocation, LocationsPeopleType]:
        """
        Bucket passengers into on-campus (by pickup location) and off-campus groups.

        Passengers living in a neighborhood listed in ``living_to_alt_pickups``
        are annotated with their alternative pickup locations. They are still
        keyed under their primary ``pickup_location`` here so capacity math
        treats them as a single pool; the LLM picks the actual location per
        passenger downstream.
        """
        valid_campus_locations = {loc.value.lower() for loc in CampusLivingLocations}
        passengers_by_location: PassengersByLocation = {}
        off_campus: LocationsPeopleType = {}

        for living_location, people in locations_people.items():
            if living_location.lower() not in valid_campus_locations:
                off_campus[living_location] = people
                continue

            living_loc_enum = self._get_living_location(living_location)
            pickup_key = self._get_pickup_location(living_loc_enum)
            alt_pickups = living_to_alt_pickups.get(living_loc_enum, [])
            passengers_by_location.setdefault(pickup_key, []).extend(
                Passenger(
                    identity=Identity(name=person[0], username=person[1]),
                    living_location=living_loc_enum,
                    pickup_location=pickup_key,
                    alt_pickup_locations=list(alt_pickups),
                )
                for person in people
            )

        return passengers_by_location, off_campus

    def _validate_capacity(
        self, driver_capacity: str, passengers_by_location: PassengersByLocation
    ) -> list[int]:
        """Parse the capacity string and verify it covers all passengers."""
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

        return driver_capacity_list

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

        Raises:
            ValueError: If invalid parameters or insufficient capacity
        """
        logger.info(
            f"_process_ride_grouping: starting - message_id={message_id}, "
            f"driver_capacity={driver_capacity}, channel_id={channel_id}"
        )

        (
            locations_people,
            usernames_reacted,
            location_found,
        ) = await self.locations_service.list_locations(message_id=message_id)

        message = await self.repo.fetch_message(channel_id, message_id)
        if not message:
            raise ValueError("Could not fetch the message content")

        combined_text = get_message_and_embed_content(message)
        event_type, end_leave_time = await self._determine_event_type(combined_text)

        if event_type == JobName.SUNDAY:
            usernames_reacted = await self._filter_class_attendees(usernames_reacted, channel_id)

        unknown_location = usernames_reacted - location_found
        if unknown_location:
            unknown_names = [str(user) for user in unknown_location]
            raise ValueError(
                f"Unknown location for user(s): {', '.join(unknown_names)}. "
                "Please ensure usernames and locations are on the spreadsheet."
            )

        passengers_by_location, off_campus = self._split_on_off_campus(locations_people)
        driver_capacity_list = self._validate_capacity(driver_capacity, passengers_by_location)

        drivers = llm_input_drivers(driver_capacity_list)
        pickups = llm_input_pickups(passengers_by_location)

        try:
            logger.info("_process_ride_grouping: calling LLM for ride grouping")
            llm_result = await asyncio.to_thread(
                self.llm_service.generate_ride_groups,
                pickups,
                drivers,
                LOCATIONS_MATRIX,
                legacy_prompt,
                custom_prompt,
                passengers_by_location,
                driver_capacity_list,
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
        logger.info(f"_process_ride_grouping: completed - generated {len(output)} output blocks")
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
        """
        Orchestrates the group rides process.

        Args:
            interaction (discord.Interaction): The Discord interaction.
            driver_capacity (str): String representing driver capacities.
            message_id (int | None, optional): Optional message ID to fetch pickups from.
            day (str | None, optional): Optional day to fetch pickups for.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.
            custom_prompt (str | None, optional): Optional custom prompt to use. Defaults to None.
        """
        await interaction.response.defer()

        logger.info(
            f"group_rides: user action - day={day}, message_id={message_id}, "
            f"driver_capacity={driver_capacity}, legacy_prompt={legacy_prompt}"
        )

        if day:
            ask_message = DAY_TO_ASK_RIDES_MESSAGE.get(JobName(day))
            if ask_message is None:
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

        await interaction.followup.send(output[0])
        for message in output[1:]:
            await interaction.channel.send(message)

    def get_pickup_location_fuzzy(self, input_loc: str) -> PickupLocations | None:
        """Delegates to RouteService.get_pickup_location_fuzzy."""
        return RouteService.get_pickup_location_fuzzy(input_loc)

    def make_route(self, locations: str, leave_time: str) -> str:
        """Delegates to RouteService.make_route."""
        return RouteService.make_route(locations, leave_time)

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

        logger.info(
            f"group_rides_api: user action - day={day}, message_id={message_id}, "
            f"driver_capacity={driver_capacity}, channel_id={channel_id}"
        )

        if day:
            ask_message = DAY_TO_ASK_RIDES_MESSAGE.get(JobName(day))
            if ask_message is None:
                raise ValueError("day must be 'friday' or 'sunday'")

            message_id = await self.locations_service._find_correct_message(ask_message, channel_id)

            if message_id is None:
                raise ValueError(f"Could not find the {day} rides message. It may not exist yet.")

        if message_id is None:
            raise ValueError("Either message_id or day must be provided")

        output = await self._process_ride_grouping(
            message_id, driver_capacity, channel_id, legacy_prompt, custom_prompt
        )

        summary = output[0] if output else ""
        groupings = [item for item in output[1:] if not item.startswith("```")]

        return {"summary": summary, "groupings": groupings}
