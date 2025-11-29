"""Service for handling LLM interactions."""

import json
import os

import tenacity
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.logger import logger
from app.core.schemas import LLMOutputError, LLMOutputNominal
from app.utils.genai.prompt import GROUP_RIDES_PROMPT, GROUP_RIDES_PROMPT_LEGACY

NUM_RETRY_ATTEMPTS = 4
# LLM_MODEL = "gemini-2.5-pro"
LLM_MODEL = "gemini-2.5-flash"

prev_response = None


# Define the callback function to print to the console
def log_retry_attempt(retry_state):
    """Logs a warning when a retry attempt is made.

    Args:
        retry_state (tenacity.RetryCallState): The current state of the retry call.
    """
    global prev_response
    logger.warning(
        f"Failed to process request, attempting retry {retry_state.attempt_number}..."
        f"Exception was: {retry_state.outcome.exception()}..."
        f"Prev response: {prev_response}"
    )


class LLMService:
    """Service for interacting with the LLM."""

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

    # Helper function to invoke the LLM with a fixed retry wait
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(NUM_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(5),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=log_retry_attempt,
    )
    def invoke_llm(self, pickups_str, drivers_str, locations_matrix, legacy_prompt=False):
        """A blocking helper function to invoke the LLM with a retry policy.

        Args:
            pickups_str (str): Formatted string of pickups.
            drivers_str (str): Formatted string of drivers.
            locations_matrix (dict): The locations distance matrix.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.

        Returns:
            dict: The parsed LLM result.
        """

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
