import asyncio
import json
from datetime import datetime, time, timedelta

import discord
import tenacity
from discord import app_commands
from discord.ext import commands
from langchain_google_genai import ChatGoogleGenerativeAI

from app.cogs.locations import Locations
from app.core.enums import FeatureFlagNames, PickupLocations
from app.core.logger import logger
from app.core.schemas import Identity, LLMOutput, LocationQuery, RidesUser
from app.utils.checks import feature_flag_enabled
from app.utils.genai.prompt import GROUP_RIDES_PROMPT
from app.utils.locations import LOCATIONS_MATRIX, lookup_time

prev_response = None

NUM_RETRY_ATTEMPTS = 5
PICKUP_ADJUSTMENT = 1


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

    Args:
        s: The input string.

    Returns:
        A list of integers.
    """
    # Remove all spaces from the string
    cleaned_string = s.replace(" ", "")

    return [int(char) for char in cleaned_string]


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
        ai_response = self.llm.invoke(
            GROUP_RIDES_PROMPT.format(
                pickups_str=pickups_str, drivers_str=drivers_str, locations_matrix=locations_matrix
            )
        )
        # For logging the previous response, can't pass variables to callback (I think)
        global prev_response
        prev_response = ai_response

        # Sometimes the LLM decides to put a code box even if it is directed not to
        if "json" in ai_response.content:
            codebox_beginning_idx = 8
            codebox_ending_idx = -3
            ret = json.loads(ai_response.content[codebox_beginning_idx:codebox_ending_idx])
        else:
            ret = json.loads(ai_response.content)

        LLMOutput.model_validate(ret)  # Throws error if does not have correct schema
        return ret

    @app_commands.command(
        name="group-rides",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def group_rides(self, interaction: discord.Interaction):
        await interaction.response.defer()

        l = Locations(self.bot)
        locations_people, usernames_reacted, location_found = await l.list_locations(
            message_id="1344460380092633088"
        )
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
        driver_capacity = "4444"

        # Data on driver capacities to send to LLM
        drivers_list = []
        for i, capacity in enumerate(parse_numbers(driver_capacity)):
            drivers_list.append(f"Driver{i} has capacity {capacity}")

        # Data on pickup locations to send to LLM
        pickups = ""
        for location in locations_people:
            filtered_names = [user[0] for user in locations_people[location]]
            pickups += f"{location}: {', '.join(filtered_names)}\n"

        try:
            logger.info("Calling LLM")
            llm_result = await asyncio.to_thread(
                self._invoke_llm_blocking, pickups, ", ".join(drivers_list), LOCATIONS_MATRIX
            )
            # 1367251697465819187
            # llm_result={'Driver0': [{'name': 'Charis Chang', 'location': 'Muir'}, {'name': 'Kristi Nakatsuka', 'location': 'ERC'}, {'name': 'Nathan Luk', 'location': 'ERC'}, {'name': 'Carly Carbery', 'location': 'Seventh'}], 'Driver2': [{'name': 'Christina Zuo', 'location': 'Innovation'}]}

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
                f"Failed to get a successful response after {NUM_RETRY_ATTEMPTS} attempts: {e}"
            )
            await interaction.followup.send(
                "Sorry, I couldn't process your request right now. Please try again later.",
                ephemeral=True,
            )
            return

        output = ""
        logger.info(f"{llm_result=}")

        def find_username(locations_people, person):
            if location in locations_people:
                for name, handle in locations_people[location]:
                    # logger.warning(f"{type(handle)}")
                    # logger.warning(f"{type(handle.name)}")
                    # logger.warning(f"{handle.name=}")
                    if name == person:
                        return handle.name
            logger.warning(f"None was returned for {locations_people=} {person=}")
            return None

        for i, driver_id in enumerate(llm_result):
            output += f"Group {i + 1}\n"
            grouped_by_location: list[list[RidesUser]] = []
            curr_location: list[RidesUser] = []

            for obj in llm_result[driver_id]:
                person = obj["name"]
                location = obj["location"]

                username = find_username(locations_people, person)

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

            curr_leave_time = time(hour=10, minute=10)
            drive_formatted = []

            def calculate_pickup_time(curr_leave_time, grouped_by_location, location, offset):
                time_between = PICKUP_ADJUSTMENT + lookup_time(
                    LocationQuery(
                        start_location=grouped_by_location[len(grouped_by_location) - offset][
                            0
                        ].location,
                        end_location=location,
                    )
                )
                dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)
                new_datetime = dummy_datetime - timedelta(minutes=time_between)
                return new_datetime.time()

            # grouped_by_location is in order by who to pickup first. Need it
            # reversed so can calculate pickup time backwards from goal leave time
            for idx, users_at_location in enumerate(reversed(grouped_by_location)):
                usernames_at_location = [ru.identity.username for ru in users_at_location]

                location = users_at_location[0].location
                if idx != 0:
                    curr_leave_time = calculate_pickup_time(
                        curr_leave_time, grouped_by_location, location, idx
                    )

                drive_formatted.append(
                    f"{' '.join(usernames_at_location)} "
                    f"{curr_leave_time.strftime('%I:%M%p').lstrip('0')} "
                    f"{location}"
                )

            if not drive_formatted:
                output += "```\nError: could not get username\n```"
            else:
                output += f"```\ndrive: {', '.join(reversed(drive_formatted))}\n```"

            output += "\n"

        await interaction.followup.send(output)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupRides(bot))
