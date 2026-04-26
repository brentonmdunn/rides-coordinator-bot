"""Service for LLM interactions."""

import json
import logging
import os

import tenacity
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.core.schemas import LLMOutputError, LLMOutputNominal
from bot.utils.genai.prompt import (
    CUSTOM_INSTRUCTIONS,
    GROUP_RIDES_PROMPT,
    GROUP_RIDES_PROMPT_LEGACY,
    PROMPT_EPILOGUE,
)
from bot.utils.locations import render_distance_markdown

logger = logging.getLogger(__name__)

# LLM_MODEL = "gemini-2.5-pro"
LLM_MODEL = "gemini-2.5-flash"
NUM_RETRY_ATTEMPTS = 4
# Fixed seed paired with temperature=0. Still not a strict guarantee of
# reproducibility (API version / model version can drift), but removes one
# source of per-call variance.
_LLM_SEED = 42


def log_retry_attempt(retry_state):
    """
    Logs a warning when a retry attempt is made.

    Args:
        retry_state (tenacity.RetryCallState): The current state of the retry call.
    """
    prev_response = None
    if retry_state.args:
        llm_self = retry_state.args[0]
        prev_response = getattr(llm_self, "_last_response", None)
    logger.warning(
        f"Failed to process request, attempting retry {retry_state.attempt_number}..."
        f"Exception was: {retry_state.outcome.exception()}..."
        f"Prev response: {prev_response}"
    )


class LLMService:
    """Service for handling Google Gemini interactions."""

    def __init__(self):
        """Initialize the LLMService.

        ``response_mime_type`` forces the Gemini API to return a JSON object,
        which removes the fragile codefence-stripping parsing path. ``seed``
        pairs with ``temperature=0`` to make outputs as reproducible as the
        API permits (useful for debugging and for best-of-N sampling later).
        """
        self.llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=0,
            response_mime_type="application/json",
            seed=_LLM_SEED,
        )

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
        """
        Invokes the LLM to group rides.

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

        # Render the adjacency graph as an all-pairs shortest-path Markdown table so
        # the LLM doesn't have to perform graph search itself. See
        # backend/docs/group_rides_pipeline.md for rationale.
        locations_matrix_md = render_distance_markdown(locations_matrix)

        if os.getenv("APP_ENV", "local") == "local":
            logger.debug(
                f"prompt={
                    prompt.format(
                        pickups_str=pickups_str,
                        drivers_str=drivers_str,
                        locations_matrix=locations_matrix_md,
                    )
                }"
            )
        else:
            logger.info(f"{pickups_str=}")
            logger.info(f"{drivers_str=}")
            logger.info(f"{locations_matrix=}")

        ai_response = self.llm.invoke(
            prompt.format(
                pickups_str=pickups_str,
                drivers_str=drivers_str,
                locations_matrix=locations_matrix_md,
            )
        )

        # Store response for retry logging via tenacity's retry_state
        self._last_response = ai_response

        logger.debug(f"Raw LLM output={ai_response}")

        # With ``response_mime_type="application/json"`` the API returns a raw
        # JSON string in ``content``. No codefence handling is required. If the
        # API ever returns something non-JSON (e.g. a safety refusal), the
        # ``JSONDecodeError`` will trigger a tenacity retry.
        llm_result = json.loads(ai_response.content)

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
