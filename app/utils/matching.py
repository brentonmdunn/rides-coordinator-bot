"""Utility functions for fuzzy matching."""

from rapidfuzz import fuzz, process

from app.core.enums import PickupLocations
from app.core.logger import logger


def get_pickup_location_fuzzy(input_loc: str) -> PickupLocations | None:
    """Fuzzy matches an input string to a PickupLocations enum member.

    Args:
        input_loc (str): The input location string to match.

    Returns:
        PickupLocations | None: The matched PickupLocations enum member, or None if no match found.
    """
    choices = {e.value: e for e in PickupLocations}

    # --- PASS 1: High Precision ---
    # Checks for whole words, handles reordering ("bamboo erc" -> "ERC... bamboo")
    result = process.extractOne(
        input_loc,
        choices.keys(),
        scorer=fuzz.token_sort_ratio,
        score_cutoff=65,  # Keep this relatively high to avoid bad guesses
    )

    if result:
        return choices[result[0]]

    # --- PASS 2: Fallback (Partial Matching) ---
    # "If a match cannot be found then try to find best match"
    # This handles substrings and typos ("seveneth" -> "Seventh mail room")
    result = process.extractOne(
        input_loc,
        choices.keys(),
        scorer=fuzz.partial_ratio,
        score_cutoff=60,  # Slightly lower cutoff for the fallback
    )

    if result:
        logger.debug(f"{result=}")
        logger.debug(f"Fallback match: '{input_loc}' -> '{result[0]}' (Score: {result[1]})")
        return choices[result[0]]

    return None
