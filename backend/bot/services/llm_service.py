"""Service for LLM interactions."""

import json
import os

import tenacity
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.core.logger import logger
from bot.core.schemas import LLMOutputError, LLMOutputNominal
from bot.utils.genai.prompt import (
    CUSTOM_INSTRUCTIONS,
    GROUP_RIDES_PROMPT,
    GROUP_RIDES_PROMPT_LEGACY,
    PROMPT_EPILOGUE,
)

# LLM_MODEL = "gemini-2.5-pro"
LLM_MODEL = "gemini-2.5-flash"
NUM_RETRY_ATTEMPTS = 4

# Global variable to store the previous response for logging purposes during retries
prev_response = None


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
    """Service for handling Google Gemini interactions."""

    def __init__(self):
        """Initialize the LLMService."""
        self.llm = ChatGoogleGenerativeAI(model=LLM_MODEL, temperature=0)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(NUM_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(5),
        retry=tenacity.retry_if_exception_type(Exception),
        before_sleep=log_retry_attempt,
    )
    def generate_ride_groups(
        self,
        pickups_str: str,
        drivers_str: str,
        locations_matrix: dict,
        legacy_prompt: bool = False,
        custom_prompt: str | None = None,
    ) -> dict:
        """Invokes the LLM to group rides.

        Args:
            pickups_str (str): Formatted string of pickups.
            drivers_str (str): Formatted string of drivers.
            locations_matrix (dict): The locations distance matrix.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.
            custom_prompt (str | None, optional): Optional custom prompt to use. Defaults to None.

        Returns:
            dict: The parsed LLM result.
        """
        if legacy_prompt:
            prompt = GROUP_RIDES_PROMPT_LEGACY
        else:
            prompt = GROUP_RIDES_PROMPT
            if custom_prompt:
                prompt += CUSTOM_INSTRUCTIONS.format(custom_instructions=custom_prompt)
            prompt += PROMPT_EPILOGUE

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

        global prev_response
        prev_response = ai_response

        logger.debug(f"Raw LLM output={ai_response}")

        def preprocess_llm_result(ai_response):
            # Attempt to be robust to optional markdown code blocks
            content = ai_response.content
            if "```json" in content:
                 try:
                    start = content.find("```json") + 7
                    end = content.rfind("```")
                    json_str = content[start:end].strip()
                    return json.loads(json_str)
                 except Exception:
                     pass
            
            # Original logic fallback
            if "json" in ai_response.content:
                codebox_beginning_idx = 8
                codebox_ending_idx = -3
                llm_result = json.loads(
                    ai_response.content[codebox_beginning_idx:codebox_ending_idx]
                )
            else:
                llm_result = json.loads(ai_response.content)
            return llm_result

        # Sometimes the LLM decides to put a code box even if it is directed not to
        llm_result = preprocess_llm_result(ai_response)

        logger.info(f"{llm_result=}")

        # Validate
        if "error" in {key.lower() for key in llm_result}:
            LLMOutputError.model_validate(llm_result)
        else:
            LLMOutputNominal.model_validate(llm_result)
            # Sometimes the LLM puts two names in one name field
            for driver_id in llm_result:
                for passenger in llm_result[driver_id]:
                    if "," in passenger["name"]:
                        raise Exception("Names cannot contain commas.")

        return llm_result
