"""Service for LLM interactions."""

import json
import logging
import os
import re

import httpx
import tenacity
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.core.schemas import LLMOutputError, LLMOutputNominal
from bot.utils.constants import (
    GEMINI_MODEL,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_WAIT_SECONDS,
)
from bot.utils.genai.prompt import (
    CUSTOM_INSTRUCTIONS,
    GROUP_RIDES_PROMPT,
    GROUP_RIDES_PROMPT_LEGACY,
    PROMPT_EPILOGUE,
)

logger = logging.getLogger(__name__)


def _is_transient_llm_error(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    msg = str(exc).lower()
    return any(kw in msg for kw in ("rate limit", "quota", "503", "429", "timeout", "connection"))


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
        """Initialize the LLMService."""
        self.llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL, temperature=0)

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(LLM_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(LLM_RETRY_WAIT_SECONDS),
        retry=tenacity.retry_if_exception(_is_transient_llm_error),
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

        # Store response for retry logging via tenacity's retry_state
        self._last_response = ai_response

        logger.debug(f"Raw LLM output={ai_response}")

        def preprocess_llm_result(ai_response):
            content = ai_response.content
            # Try to extract from ```json ... ``` or ``` ... ``` code block
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except Exception:
                    pass
            # Fall back to raw parse
            return json.loads(content.strip())

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
