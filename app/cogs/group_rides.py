import asyncio  # New import
import json

import discord
import tenacity
from discord import app_commands
from discord.ext import commands
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import time, datetime, timedelta
from app.core.enums import FeatureFlagNames
from app.core.logger import logger
from app.utils.checks import feature_flag_enabled
from app.utils.genai.prompt import GROUP_RIDES_PROMPT
from app.utils.locations import LOCATIONS_MATRIX, lookup_time
from app.core.schemas import LocationQuery

from app.cogs.locations import Locations

prev_response = None

NUM_RETRY_ATTEMPTS = 5

# Define the callback function to print to the console
def log_retry_attempt(retry_state):
    global prev_response
    logger.warning(
        f"Failed to process request, attempting retry {retry_state.attempt_number}...Exception was: {retry_state.outcome.exception()}...Prev response: {prev_response}"
    )
    # You can also access other useful information from retry_state
    # print(f"Exception was: {retry_state.outcome.exception()}")
    # print(f"Waiting for {retry_state.next_action.sleep} seconds...")


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

    # Convert each character (which should be a digit) to an integer
    # This also handles the case of a single-digit input like "7"
    return [int(char) for char in cleaned_string]


class GroupRides(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        # self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-pro")

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
        global prev_response
        prev_response = ai_response
        if "json" in ai_response.content:
            ai_response = ai_response.content[8:-3]
            ret = json.loads(ai_response)
        else:
            ret = json.loads(ai_response.content)

        # TODO: pydantic validation on the json...just bc it is valid json doesn't 
        # mean that is json that we want 
        return ret 
    @app_commands.command(
        name="group-rides",
        description="Uses GenAI to group riders with drivers",
    )
    @feature_flag_enabled(FeatureFlagNames.BOT)
    async def group_rides(self, interaction: discord.Interaction):
        logger.info("group rides called")

        l = Locations(self.bot)
        # locations_people, usernames_reacted, location_found = await l.list_locations(message_id="1379958145656553665")
        locations_people = {
            "Seventh": [("carly", "@carbear")],
            "ERC": [("nathan luk", "@bleh"), ("kristi", "@kristi")],
            "Muir": [("charis", "@avo"), ("ros", "@ros")],
            "Sixth": [("alice", "@mango")],
            "Warren": [("sydney", "@syd"), ("laurent", "@laurent")], 
            "Rita": [("kendra", "@kendra")]
        }
        # locations_people = {
        #     "Seventh": [("carly", "@carbear")],
        #     "Muir": [("charis", "@avo")],
        #     "ERC": [("nathan luk", "@bleh")],
        #     "Sixth": [("alice", "@brentond")],
        # }
        driver_capacity = "44134"
        drivers_list = []
        for i, capacity in enumerate(parse_numbers(driver_capacity)):
            drivers_list.append(f"Driver{i} has capacity {capacity}")

        pickups = ""
        for location in locations_people:
            filtered = [p[0] for p in locations_people[location]]
            pickups += f"{location}: {", ".join(filtered)}\n"
        logger.info(f"{pickups=}")
        logger.info(f"{drivers_list=}")

        # await interaction.response.send_message("Test")
        # return
        await interaction.response.defer()
        # The prompt generation is a quick operation, but the API call is slow
        # pickups = """
        # 🏫 [8] Scholars (no Eighth)
        # (2) seventh: carly, irene
        # (1) erc: clement, kristi
        # (2) muir: charis, rosalyn
        # (2) sixth: alice, emily p
        # 🏠 [3] Warren + Pepper Canyon
        # (2) warren (equality ln): nathan leung, emily yip
        # (1) pcyn (innovation ln): josh k
        # 🏡 [2] Rita + Eighth
        # (2) rita: hannah ng, kendra
        # """

        try:
            logger.info("Calling LLM")
            # result = await asyncio.to_thread(
            #     self._invoke_llm_blocking, pickups, ", ".join(drivers_list), LOCATIONS_MATRIX
            # )
            # result = {'Driver0': [['charis', 'Muir'], ['alice', 'Sixth'], ['nathan luk', 'ERC'], ['carly', 'Seventh']]}
            result={'Driver2': [{'name': 'kendra', 'location': 'Rita'}], 'Driver3': [{'name': 'nathan luk', 'location': 'ERC'}, {'name': 'kristi', 'location': 'ERC'}, {'name': 'carly', 'location': 'Seventh'}], 'Driver0': [{'name': 'charis', 'location': 'Muir'}, {'name': 'ros', 'location': 'Muir'}, {'name': 'alice', 'location': 'Sixth'}], 'Driver1': [{'name': 'sydney', 'location': 'Warren'}, {'name': 'laurent', 'location': 'Warren'}]}


        except Exception as e:
            # Handle the case where all retries fail
            logger.error(f"Failed to get a successful response after {NUM_RETRY_ATTEMPTS} attempts: {e}")
            # Use followup to send the error message
            await interaction.followup.send(
                "Sorry, I couldn't process your request right now. Please try again later.",
                ephemeral=True,
            )
        # Use followup to send the final response
        output = ""
        logger.info(f"{result=}")
        for i, driver in enumerate(result):
            logger.info(f"Looking at {driver=}")
            output += f"Group {i+1}\n"
            grouped_by_college = []
            curr_college = []
            # for person, college in result[driver]:
            for obj in result[driver]:
                person = obj['name']
                college= obj['location']
                logger.info(f"Looking at {person=} {driver=}")
                username = None
                if college.lower() in [l.lower() for l in locations_people]:
                    for name, handle in locations_people[college]:
                        if name == person:
                            username = handle
                logger.info(f"{username=}")
                output += f"- {person} ({college}, @{username[1:]})\n"
                logger.info(f"Before: {curr_college=}")
                if len(curr_college) == 0 or college == curr_college[-1][1]:
                    curr_college.append((person, college, username))
                else:
                    grouped_by_college.append(curr_college)
                    curr_college = []
                    curr_college.append((person, college, username))
                logger.info(f"After: {curr_college=}")
                logger.info(f"{grouped_by_college=}")
                
            grouped_by_college.append(curr_college)

            PICKUP_CONSTANT = 1
            curr_leave_time = time(hour=10)
            drive_formatted = []
            logger.info("--------------------------------------")
            for i, grouping in enumerate(reversed(grouped_by_college)):
                logger.info(f"{grouping=}")
                usernames_at_location = [u for _, _, u in grouping]
                college = grouping[0][1]
                if i != 0:
                    logger.warning(f"{grouped_by_college=}")
                    time_between = PICKUP_CONSTANT + lookup_time(
                        LocationQuery(
                            start_location=grouped_by_college[len(grouped_by_college)-i][0][1], 
                            end_location=college
                        )
                    )
                    logger.info(f"{time_between=}")
                    dummy_datetime = datetime.combine(datetime.today(), curr_leave_time)

                    new_datetime = dummy_datetime - timedelta(minutes=time_between)

                    curr_leave_time = new_datetime.time()
                    
                drive_formatted.append(f"{" ".join(usernames_at_location)} {curr_leave_time} {college}")


    


            logger.info(f"{drive_formatted=}")
            # Add code box for copy paste
            if not drive_formatted:
                output += "```\nError: could not get username\n```"
            else:
                output += f"```\ndrive: {", ".join(reversed(drive_formatted))}\n```"

            output += "\n"

        await interaction.followup.send(output)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroupRides(bot))
