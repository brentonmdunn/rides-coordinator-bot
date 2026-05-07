"""Service for LLM interactions."""

import json
import logging
import os

import tenacity
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.core.schemas import LLMOutputError, LLMOutputNominal
from bot.services.assignment_validator import format_repair_instructions, validate_assignment
from bot.services.ride_grouping import PassengersByLocation
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
# Number of repair attempts to make if the LLM output fails semantic
# validation. Each repair attempt feeds the previous output + the specific
# violations back to the model.
MAX_REPAIR_ATTEMPTS = 2


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
        """
        Initialize the LLMService.

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
        passengers_by_location: PassengersByLocation | None = None,
        driver_capacity_list: list[int] | None = None,
    ) -> dict:
        """
        Invokes the LLM to group rides.

        When ``passengers_by_location`` and ``driver_capacity_list`` are provided,
        the output is passed through :func:`validate_assignment` and, if any
        semantic violations are found, the LLM is re-prompted with its previous
        output and the specific violations (up to :data:`MAX_REPAIR_ATTEMPTS`
        times). When those structured inputs are not provided, only shape-level
        validation runs (backward compatible behavior).

        Args:
            pickups_str (str): Formatted string of pickups.
            drivers_str (str): Formatted string of drivers.
            locations_matrix (dict): The locations distance matrix.
            legacy_prompt (bool, optional): Whether to use the legacy prompt. Defaults to False.
            custom_prompt (str | None, optional): Optional custom prompt to use. Defaults to None.
            passengers_by_location (PassengersByLocation | None, optional):
                Structured passenger data used for semantic validation. If None,
                semantic validation is skipped.
            driver_capacity_list (list[int] | None, optional):
                Per-driver capacity used for capacity validation. If None,
                capacity validation is skipped.

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

        base_prompt = prompt.format(
            pickups_str=pickups_str,
            drivers_str=drivers_str,
            locations_matrix=locations_matrix_md,
        )

        if os.getenv("APP_ENV", "local") == "local":
            logger.debug(f"prompt={base_prompt}")
        else:
            logger.info(f"{pickups_str=}")
            logger.info(f"{drivers_str=}")
            logger.info(f"{locations_matrix=}")

        current_prompt = base_prompt
        last_violations: list[str] = []

        for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
            ai_response = self.llm.invoke(current_prompt)

            # Store response for retry logging via tenacity's retry_state
            self._last_response = ai_response

            logger.debug(f"Raw LLM output (attempt {attempt})={ai_response}")

            # With ``response_mime_type="application/json"`` the API returns a raw
            # JSON string in ``content``. If the API ever returns something
            # non-JSON (e.g. a safety refusal), the ``JSONDecodeError`` will
            # propagate up and trigger a tenacity retry on the whole call.
            llm_result = json.loads(ai_response.content)

            logger.info(f"{llm_result=}")

            # Shape-only validation: either an error dict or a driver->passengers dict.
            if "error" in {key.lower() for key in llm_result}:
                LLMOutputError.model_validate(llm_result)
                return llm_result

            LLMOutputNominal.model_validate(llm_result)

            # Sometimes the LLM puts two names in one name field. Treat as a
            # semantic violation so the repair loop can handle it instead of
            # bubbling out and retrying the identical prompt.
            comma_violations = [
                f"Passenger entry in driver '{driver_id}' has a comma in the name field: "
                f"'{passenger['name']}'. Split into separate entries."
                for driver_id, passengers in llm_result.items()
                for passenger in passengers
                if "," in passenger.get("name", "")
            ]

            semantic_violations: list[str] = []
            if passengers_by_location is not None and driver_capacity_list is not None:
                semantic_violations = validate_assignment(
                    llm_result, passengers_by_location, driver_capacity_list
                )

            violations = comma_violations + semantic_violations

            if not violations:
                return llm_result

            last_violations = violations
            logger.warning(f"LLM output violated constraints on attempt {attempt}: {violations}")

            if attempt >= MAX_REPAIR_ATTEMPTS:
                break

            current_prompt = base_prompt + format_repair_instructions(
                previous_output=ai_response.content,
                violations=violations,
            )

        raise ValueError(
            f"LLM output failed validation after {MAX_REPAIR_ATTEMPTS + 1} attempts. "
            f"Violations: {last_violations}"
        )
