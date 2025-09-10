import asyncio
import json
from datetime import datetime, time, timedelta

import discord
import tenacity
from discord import app_commands
from discord.ext import commands
from langchain_google_genai import ChatGoogleGenerativeAI

from app.cogs.locations import Locations
from app.core.enums import ChannelIds, FeatureFlagNames, PickupLocations
from app.core.logger import logger
from app.core.schemas import Identity, LLMOutput, LocationQuery, RidesUser
from app.utils.checks import feature_flag_enabled
from app.utils.custom_exceptions import NoMatchingMessageFoundError
from app.utils.genai.prompt import GROUP_RIDES_PROMPT
from app.utils.locations import LOCATIONS_MATRIX, lookup_time

prev_response = None

NUM_RETRY_ATTEMPTS = 5
PICKUP_ADJUSTMENT = 1

map_links = {
    PickupLocations.SIXTH: "https://maps.app.goo.gl/z8cffnYwLi1sgYcf8",
    PickupLocations.SEVENTH: "https://maps.app.goo.gl/qcuCR5q6Tx2EEn9c9",
}


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


def find_username(locations_people, person, location):
    if location in locations_people:
        for name, handle in locations_people[location]:
            if name == person:
                if isinstance(handle, str):
                    return handle
                return handle.name
    logger.warning(f"None was returned for {locations_people=} {person=}")
    return None


def count_tuples(data_dict):
    """
    Counts the total number of tuples across all lists in a dictionary.
    """
    total_tuples = 0
    # Iterate through the values of the dictionary
    for people_list in data_dict.values():
        # Add the number of items in the current list to the total
        total_tuples += len(people_list)
    return total_tuples


def is_enough_capacity(driver_capacity_list: list[int], locations_people) -> bool:
    """True if enough driver capacity, false otherwise"""
    rider_count = count_tuples(locations_people)
    return sum(driver_capacity_list) >= rider_count


def calculate_pickup_time(curr_leave_time, grouped_by_location, location, offset):
    time_between = PICKUP_ADJUSTMENT + lookup_time(
        LocationQuery(
            start_location=grouped_by_location[len(grouped_by_location) - offset][0].location,
            end_location=location,
        )
    )
    dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
    new_datetime = dummy_datetime - timedelta(minutes=time_between)
    return new_datetime.time()


def llm_input_drivers(driver_capacity):
    """Data on driver capacities to send to LLM"""
    drivers_list = []
    for i, capacity in enumerate(parse_numbers(driver_capacity)):
        drivers_list.append(f"Driver{i} has capacity {capacity}")
    return drivers_list


def llm_input_pickups(locations_people):
    """Data on pickup locations to send to LLM"""
    pickups = ""
    for location in locations_people:
        filtered_names = [user[0] for user in locations_people[location]]
        pickups += f"{location}: {', '.join(filtered_names)}\n"
    return pickups


def form_output(llm_result, locations_people, curr_leave_time):
    output = ""

    for i, driver_id in enumerate(llm_result):
        output += f"Group {i + 1}\n"
        grouped_by_location: list[list[RidesUser]] = []
        curr_location: list[RidesUser] = []

        for obj in llm_result[driver_id]:
            person = obj["name"]
            location = obj["location"]

            username = find_username(locations_people, person, location)

            rides_user = RidesUser(
                identity=Identity(name=obj["name"], username=username), location=location
            )

            output += (
                f"- {rides_user.identity.name} "
                f"({rides_user.location}, "
                f"{rides_user.identity.username})\n"
            )

            # New group or part of same group as prev
            if len(curr_location) == 0 or location == curr_location[-1].location:
                curr_location.append(rides_user)
            # Need to end curr group and create new group
            else:
                grouped_by_location.append(curr_location)
                curr_location: list[RidesUser] = []
                curr_location.append(rides_user)

        grouped_by_location.append(curr_location)

        drive_formatted = []

        # grouped_by_location is in order by who to pickup first. Need it
        # reversed so can calculate pickup time backwards from goal leave time
        for idx, users_at_location in enumerate(reversed(grouped_by_location)):
            usernames_at_location = [ru.identity.username for ru in users_at_location]

            location = users_at_location[0].location
            if idx != 0:
                curr_leave_time = calculate_pickup_time(
                    curr_leave_time, grouped_by_location, location, idx
                )

            base_string = (
                f"{' '.join(usernames_at_location)} "
                f"{curr_leave_time.strftime('%I:%M%p').lstrip('0')} "
                f"{location}"
            )

            if location in map_links:
                formatted_string = f"{base_string} ([link]({map_links[location]}))"
            else:
                formatted_string = base_string

            drive_formatted.append(formatted_string)

        if not drive_formatted:
            output += "```\nError: could not get username\n```"
        else:
            output += f"```\ndrive: {', '.join(reversed(drive_formatted))}\n```"

        output += "\n"
    return output


def do_sunday_rides():
    """
    Checks if a given datetime is between 9 PM on Friday and 11 PM on Sunday.

    Returns:
        True if the datetime is within the specified window, False otherwise.
    """
    current_datetime = datetime.datetime.now()
    day_of_week = current_datetime.weekday()

    # The conditional statement
    return (
        (day_of_week == 4 and current_datetime.hour >= 21)
        or (day_of_week == 5)
        or (day_of_week == 6 and current_datetime.hour < 23)
    )


class GroupRides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro")

    # Helper function to invoke the LLM with a fixed retry wait
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(NUM_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(5),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=log_retry_attempt,
    )
    def _invoke_llm_blocking(self, pickups_str, drivers_str, locations_matrix):
        """A blocking helper function to invoke the LLM with a retry policy."""
        logger.info("Calling LLM")
        logger.info(
            f"prompt={
                GROUP_RIDES_PROMPT.format(
                    pickups_str=pickups_str,
                    drivers_str=drivers_str,
                    locations_matrix=locations_matrix,
                )
            }"
        )
        ai_response = self.llm.invoke(
            GROUP_RIDES_PROMPT.format(
                pickups_str=pickups_str, drivers_str=drivers_str, locations_matrix=locations_matrix
            )
        )
        # For logging the previous response, can't pass variables to callback (I think)
        global prev_response
        prev_response = ai_response

        logger.info(f"Raw LLM output={ai_response}")

        # Sometimes the LLM decides to put a code box even if it is directed not to
        if "json" in ai_response.content:
            codebox_beginning_idx = 8
            codebox_ending_idx = -3
            llm_result = json.loads(ai_response.content[codebox_beginning_idx:codebox_ending_idx])
        else:
            llm_result = json.loads(ai_response.content)

        LLMOutput.model_validate(llm_result)  # Throws error if does not have correct schema
        logger.info(f"{llm_result=}")
        return llm_result

    @app_commands.command(
        name="group-rides",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    @discord.app_commands.describe(
        driver_capacity="Optional area to list driver capacities, default 44444",
        message_id="Optional message ID to look at at specific message",
    )
    async def group_rides(
        self,
        interaction: discord.Interaction,
        driver_capacity: str = "44444",
        message_id: str | None = None,
    ):
        await interaction.response.defer()

        location_service = Locations(self.bot)

        try:
            if message_id is not None:
                (
                    locations_people,
                    usernames_reacted,
                    location_found,
                ) = await location_service.list_locations(message_id=message_id)
                channel = self.bot.get_channel(int(ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS))
                message = await channel.fetch_message(int(message_id))
                if "sunday" in message.content.lower():
                    end_leave_time = time(hour=10, minute=10)
                elif "friday" in message.content.lower():
                    end_leave_time = time(hour=19, minute=10)
                else:
                    await interaction.followup.send(
                        """Error: Please ensure that "friday" or "sunday" is written in message.""",
                    )
                    return
            elif do_sunday_rides():
                (
                    locations_people,
                    usernames_reacted,
                    location_found,
                ) = await location_service.list_locations(day="sunday")
                end_leave_time = time(hour=10, minute=10)
            else:
                (
                    locations_people,
                    usernames_reacted,
                    location_found,
                ) = await location_service.list_locations(day="friday")
                end_leave_time = time(hour=19, minute=10)
        except NoMatchingMessageFoundError:
            await interaction.followup.send(
                "No rides announcement message found.",
                ephemeral=True,
            )
            return

        unknown_location = usernames_reacted - location_found
        if unknown_location:
            unknown_names = [str(user) for user in unknown_location]
            await interaction.followup.send(
                f"Error: Please ensure that {', '.join(unknown_names)} username(s) are on the [spreadsheet](https://docs.google.com/spreadsheets/d/1uQNUy57ea23PagKhPEmNeQPsP2BUTVvParRrE9CF_Tk/edit?gid=0#gid=0).",
            )
            return

        # Workaround since capitalization is not the same between services
        # Fix is issue #107 https://github.com/brentonmdunn/rides-coordinator-bot/issues/107
        locations_people_copy = {}
        for key in locations_people:
            if key == "erc":
                locations_people_copy[PickupLocations.ERC] = locations_people[key]
            else:
                locations_people_copy[key.title()] = locations_people[key]
        locations_people = locations_people_copy
        # locations_people = {
        #     "Seventh": [("carly", "@carbear")],
        #     "ERC": [("nathan luk", "@bleh"), ("kristi", "@kristi")],
        #     "Muir": [("charis", "@avo"), ("ros", "@ros")],
        #     "Sixth": [("alice", "@mango")],
        #     "Warren": [("sydney", "@syd"), ("laurent", "@laurent")],
        #     "Rita": [("kendra", "@kendra")]
        # }
        # locations_people = {
        #     "Seventh": [("carly", "@carbear")],
        #     "Muir": [("charis", "@avo")],
        #     "ERC": [("nathan luk", "@bleh")],
        #     "Sixth": [("alice", "@brentond")],
        # }
        # locations_people = {
        #     "Seventh": [("carly", "@carbear")],
        #     "Muir": [("charis", "@avo")],
        #     "ERC": [("nathan luk", "@bleh")],
        # }
        # driver_capacity = "44134"
        # driver_capacity = "44"

        if not is_enough_capacity(parse_numbers(driver_capacity), locations_people):
            await interaction.followup.send(
                f"Error: More people need a ride than we have drivers.\n"
                f"Num need rides: {count_tuples(locations_people)}\n"
                f"Num drivers: {len(parse_numbers(driver_capacity))}\n"
                f"Driver capacity: {sum(parse_numbers(driver_capacity))}"
            )
            return

        # Data on driver capacities to send to LLM
        drivers_list = llm_input_drivers(driver_capacity)

        # Data on pickup locations to send to LLM
        pickups = llm_input_pickups(locations_people)

        try:
            llm_result = await asyncio.to_thread(
                self._invoke_llm_blocking, pickups, ", ".join(drivers_list), LOCATIONS_MATRIX
            )
            # 1367251697465819187
            # llm_result = {
            #     "Driver0": [
            #         {"name": "Charis Chang", "location": "Muir"},
            #         {"name": "Kristi Nakatsuka", "location": "ERC"},
            #         {"name": "Nathan Luk", "location": "ERC"},
            #         {"name": "Carly Carbery", "location": "Seventh"},
            #     ],
            #     "Driver2": [{"name": "Christina Zuo", "location": "Innovation"}],
            # }

            # llm_result={'Driver2': [{'name': 'kendra', 'location': 'Rita'}], 'Driver3': [{'name': 'nathan luk', 'location': 'ERC'}, {'name': 'kristi', 'location': 'ERC'}, {'name': 'carly', 'location': 'Seventh'}], 'Driver0': [{'name': 'charis', 'location': 'Muir'}, {'name': 'ros', 'location': 'Muir'}, {'name': 'alice', 'location': 'Sixth'}], 'Driver1': [{'name': 'sydney', 'location': 'Warren'}, {'name': 'laurent', 'location': 'Warren'}]} # noqa
            # llm_result={'Driver0': [{'name': 'charis', 'location': 'Muir'}, {'name': 'alice', 'location': 'Sixth'}, {'name': 'nathan luk', 'location': 'ERC'}, {'name': 'carly', 'location': 'Seventh'}]} # noqa
            # llm_result = {
            #     "Driver0": [
            #         {"name": "charis", "location": "Muir"},
            #         {"name": "nathan luk", "location": "ERC"},
            #         {"name": "carly", "location": "Seventh"},
            #     ]
            # }

        except Exception as e:
            logger.error(
                f"Failed to get a successful LLM response after {NUM_RETRY_ATTEMPTS} attempts: {e}"
            )
            await interaction.followup.send(
                "Sorry, I couldn't process your request right now. Please try again later.",
                ephemeral=True,
            )
            return

        output = form_output(llm_result, locations_people, end_leave_time)

        await interaction.followup.send(output)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupRides(bot))
