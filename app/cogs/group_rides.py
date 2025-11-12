import asyncio
import json
import os
from datetime import datetime, time, timedelta

import discord
import tenacity
from discord import app_commands
from discord.ext import commands
from langchain_google_genai import ChatGoogleGenerativeAI

from app.cogs.locations import Locations
from app.core.enums import (
    AskRidesMessage,
    CampusLivingLocations,
    ChannelIds,
    FeatureFlagNames,
    PickupLocations,
)
from app.core.logger import log_cmd, logger
from app.core.schemas import (
    Identity,
    LLMOutputError,
    LLMOutputNominal,
    LocationQuery,
    Passenger,
)
from app.utils.channel_whitelist import LOCATIONS_CHANNELS_WHITELIST, cmd_is_allowed
from app.utils.checks import feature_flag_enabled
from app.utils.constants import MAP_LINKS
from app.utils.genai.prompt import GROUP_RIDES_PROMPT, GROUP_RIDES_PROMPT_LEGACY
from app.utils.locations import LOCATIONS_MATRIX, lookup_time
from app.utils.parsing import get_message_and_embed_content

prev_response = None

NUM_RETRY_ATTEMPTS = 4
PICKUP_ADJUSTMENT = 1

# LLM_MODEL = "gemini-2.5-pro"
LLM_MODEL = "gemini-2.5-flash"


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


# Define the callback function to print to the console
def log_retry_attempt(retry_state):
    global prev_response
    logger.warning(
        f"Failed to process request, attempting retry {retry_state.attempt_number}..."
        f"Exception was: {retry_state.outcome.exception()}..."
        f"Prev response: {prev_response}"
    )


def parse_numbers(s: str) -> list[int]:
    """
    Parses a string of single-digit numbers and returns a list of integers.

    The input string can have numbers separated by spaces or no spaces at all.
    Each number in the input string must be a single digit from 0 to 9.

    Example input: "4 4 4" or "444"

    Args:
        s: The input string.

    Returns:
        A list of integers.
    """
    # Remove all spaces from the string
    cleaned_string = s.replace(" ", "")

    return [int(char) for char in cleaned_string]


def find_passenger(locations_people: PassengersByLocation, person: str, location: str) -> Passenger:
    if location in locations_people:
        for p in locations_people[location]:
            if p.identity.name == person:
                return p
    logger.warning(f"None was returned for {locations_people=} {person=}")
    return None


def count_tuples(data_dict: PassengersByLocation) -> int:
    """
    Counts the total number of tuples across all lists in a dictionary.
    """
    total_tuples = 0
    # Iterate through the values of the dictionary
    for people_list in data_dict.values():
        # Add the number of items in the current list to the total
        total_tuples += len(people_list)
    return total_tuples


def is_enough_capacity(
    driver_capacity_list: list[int], locations_people: PassengersByLocation
) -> bool:
    """True if enough driver capacity, false otherwise"""
    rider_count = count_tuples(locations_people)
    return sum(driver_capacity_list) >= rider_count


def calculate_pickup_time(
    curr_leave_time: datetime.time, grouped_by_location, location: str, offset: int
) -> datetime.time:
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
    """Data on driver capacities to send to LLM"""
    drivers_list = []
    for i, capacity in enumerate(driver_capacity):
        drivers_list.append(f"Driver{i} has capacity {capacity}")
    return ", ".join(drivers_list)


def llm_input_pickups(locations_people: PassengersByLocation) -> str:
    """Data on pickup locations to send to LLM"""
    pickups = ""
    for location in locations_people:
        filtered_names = [person.identity.name for person in locations_people[location]]
        pickups += f"{location}: {', '.join(filtered_names)}\n"
    return pickups


def create_output(
    llm_result: dict[str, list[dict[str, str]]],
    locations_people: LocationsPeopleType,
    end_leave_time: datetime.time,
    off_campus: LocationsPeopleType,
):
    overall_summary = "==== summary ====\n"
    output_list = []

    for driver_id in llm_result:
        curr_leave_time = end_leave_time
        grouped_by_location: list[list[Passenger]] = []
        curr_location: list[Passenger] = []

        for obj in llm_result[driver_id]:
            person = obj["name"]
            location = obj["location"]

            passenger = find_passenger(locations_people, person, location)

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


class GroupRides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

    # Helper function to invoke the LLM with a fixed retry wait
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(NUM_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(5),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=log_retry_attempt,
    )
    def _invoke_llm(self, pickups_str, drivers_str, locations_matrix, legacy_prompt=False):
        """A blocking helper function to invoke the LLM with a retry policy."""

        prompt = GROUP_RIDES_PROMPT_LEGACY if legacy_prompt else GROUP_RIDES_PROMPT

        if os.getenv("APP_ENV", "local") == "local":
            logger.debug(
                f"prompt={
                    prompt.format(
                        pickups_str=pickups_str,
                        drivers_str=drivers_str,
                        locations_matrix=locations_matrix,
                    )
                }"
            )
        else:
            logger.info(f"{pickups_str=}")
            logger.info(f"{drivers_str=}")
            logger.info(f"{locations_matrix=}")

        ai_response = self.llm.invoke(
            prompt.format(
                pickups_str=pickups_str, drivers_str=drivers_str, locations_matrix=locations_matrix
            )
        )

        # For logging the previous response, can't pass variables to callback (I think)
        global prev_response
        prev_response = ai_response

        logger.debug(f"Raw LLM output={ai_response}")

        def preprocess_llm_result(ai_response):
            if "json" in ai_response.content:
                codebox_beginning_idx = 8
                codebox_ending_idx = -3
                llm_result = json.loads(
                    ai_response.content[codebox_beginning_idx:codebox_ending_idx]
                )
            else:
                llm_result = json.loads(ai_response.content)
            return llm_result

        def validate_llm_result(llm_result):
            if "error" in {key.lower() for key in llm_result}:
                LLMOutputError.model_validate(llm_result)
            else:
                LLMOutputNominal.model_validate(llm_result)
                # Sometimes the LLM puts two names in one name field
                for driver_id in llm_result:
                    for passenger in llm_result[driver_id]:
                        if "," in passenger["name"]:
                            raise Exception("Names cannot contain commas.")

        # Sometimes the LLM decides to put a code box even if it is directed not to
        llm_result = preprocess_llm_result(ai_response)

        logger.info(f"{llm_result=}")

        # Throws error if does not have correct schema
        validate_llm_result(llm_result)

        return llm_result

    async def _group_rides(
        self,
        interaction: discord.Interaction,
        message_id,
        driver_capacity: str,
        legacy_prompt: bool = False,
    ):
        await interaction.response.defer()
        location_service = Locations(self.bot)
        (
            locations_people,
            usernames_reacted,
            location_found,
        ) = await location_service.list_locations(message_id=message_id)
        channel = self.bot.get_channel(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS))
        message = await channel.fetch_message(int(message_id))
        combined_text = get_message_and_embed_content(message)

        if "sunday" in combined_text:
            end_leave_time = time(hour=10, minute=10)
            class_message_id = await location_service._find_correct_message(
                AskRidesMessage.SUNDAY_CLASS,
            )
            if class_message_id is not None:
                (
                    _,
                    class_usernames_reacted,
                    _,
                ) = await location_service.list_locations(message_id=class_message_id)
                usernames_reacted - class_usernames_reacted

        elif "friday" in combined_text:
            end_leave_time = time(hour=19, minute=10)
        else:
            raise ValueError(
                """Error: Please ensure that "friday" or "sunday" is written in message.""",
            )

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
        for living_location in locations_people:
            if living_location.lower() not in [
                location.value.lower() for location in CampusLivingLocations
            ]:
                off_campus[living_location] = locations_people[living_location]
                continue

            def get_living_location(loc):
                # Workaround since capitalization is not the same between services
                # Fix is issue #107 https://github.com/brentonmdunn/rides-coordinator-bot/issues/107
                if loc == "erc":
                    return CampusLivingLocations.ERC
                return loc.title()

            def get_pickup_location(loc):
                return living_to_pickup[get_living_location(loc)]

            pickup_key = get_pickup_location(living_location)

            # Get the existing list or create a new one, then extend it
            passengers_by_location.setdefault(pickup_key, []).extend(
                Passenger(
                    identity=Identity(
                        name=person[0], username=person[1].name if person[1] else None
                    ),
                    living_location=get_living_location(living_location),
                    pickup_location=pickup_key,  # Reuse the calculated key
                )
                for person in locations_people[living_location]
            )

        if not is_enough_capacity(parse_numbers(driver_capacity), passengers_by_location):
            await interaction.followup.send(
                f"Error: More people need a ride than we have drivers.\n"
                f"Num need rides: {count_tuples(locations_people)}\n"
                f"Num drivers: {len(parse_numbers(driver_capacity))}\n"
                f"Driver capacity: {sum(parse_numbers(driver_capacity))}"
            )
            return

        # Data on driver capacities to send to LLM
        try:
            drivers = llm_input_drivers(parse_numbers(driver_capacity))
        except ValueError:
            await interaction.followup.send(
                "Error: `driver_capacity` must only contain integers.",
                ephemeral=True,
            )
            return
        # Data on pickup locations to send to LLM
        pickups = llm_input_pickups(passengers_by_location)

        try:
            llm_result = await asyncio.to_thread(
                self._invoke_llm, pickups, drivers, LOCATIONS_MATRIX, legacy_prompt
            )

        except Exception as e:
            logger.error(
                f"Failed to get a successful LLM response after {NUM_RETRY_ATTEMPTS} attempts: {e}"
            )
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

    @app_commands.command(
        name="group-rides-friday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_friday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        location_service = Locations(self.bot)
        message_id = await location_service._find_correct_message(AskRidesMessage.FRIDAY_FELLOWSHIP)
        await self._group_rides(interaction, message_id, driver_capacity, legacy_prompt)

    @app_commands.command(
        name="group-rides-sunday",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_sunday(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        location_service = Locations(self.bot)
        message_id = await location_service._find_correct_message(AskRidesMessage.SUNDAY_SERVICE)
        await self._group_rides(interaction, message_id, driver_capacity, legacy_prompt)

    @app_commands.command(
        name="group-rides-sunday-by-message-id",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        message_id="The message ID to fetch pickups from",
        driver_capacity="Optional area to list driver capacities, default 5 drivers with capacity=4 each",  # noqa: E501
    )
    @log_cmd
    async def group_rides_message_id(
        self,
        interaction: discord.Interaction,
        message_id: str,
        driver_capacity: str = "44444",
        legacy_prompt: bool = False,
    ):
        if not await cmd_is_allowed(
            interaction, interaction.channel_id, LOCATIONS_CHANNELS_WHITELIST
        ):
            return
        await self._group_rides(interaction, message_id, driver_capacity, legacy_prompt)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupRides(bot))
