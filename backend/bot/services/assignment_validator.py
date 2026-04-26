"""Semantic validation of LLM assignment output.

`LLMOutputNominal` only validates shape (dict of list of {name, location}).
Even a shape-valid output can be wrong: wrong passenger names, wrong locations,
capacity violations, or missing/duplicate passengers. This module adds those
checks and formats violations as human-readable strings suitable for feeding
back to the LLM in a repair prompt.
"""

from __future__ import annotations

import re

from bot.core.schemas import Passenger
from bot.services.ride_grouping import PassengersByLocation

_DRIVER_ID_RE = re.compile(r"^Driver(\d+)$")


def _normalize_location(raw: str) -> str:
    """Lowercase + collapse whitespace for forgiving location string comparison.

    The bot sometimes passes the enum value ("Sixth loop") and the LLM sometimes
    shortens it ("Sixth") or echoes the input verbatim. Comparing normalized
    prefixes avoids false positives from innocuous formatting differences while
    still catching real mistakes like "Rita" vs "Innovation".
    """
    return " ".join(raw.lower().split())


def _allowed_pickup_values(passenger: Passenger) -> set[str]:
    """Return normalized pickup-location strings a passenger may be assigned.

    Every passenger has a single primary ``pickup_location``. The helper
    returns both the full enum value and a single-word short form so the
    LLM can use either style. The Marshall-flex change (a follow-up commit)
    extends this function to also return alternative locations.
    """
    pickup = passenger.pickup_location
    full = _normalize_location(str(pickup))
    short = full.split()[0] if full else full
    return {full, short}


def validate_assignment(
    llm_result: dict[str, list[dict[str, str]]],
    passengers_by_location: PassengersByLocation,
    driver_capacity_list: list[int],
) -> list[str]:
    """Return a list of human-readable violations; empty list means valid.

    Checks performed:
      * every input passenger appears exactly once in the assignment
      * no phantom passenger names
      * each passenger is assigned to an allowed pickup location
      * ``DriverN`` passenger count does not exceed capacity ``N``
      * entries are well-formed ``{name, location}`` objects

    Args:
        llm_result: Parsed LLM output, a dict ``driver_id -> [{name, location}, ...]``.
        passengers_by_location: The expected passengers keyed by pickup location.
        driver_capacity_list: ``[cap0, cap1, ...]`` indexed by ``DriverN``.

    Returns:
        A (possibly empty) list of violation messages.
    """
    violations: list[str] = []

    name_to_passenger: dict[str, Passenger] = {}
    for passengers in passengers_by_location.values():
        for p in passengers:
            name_to_passenger[p.identity.name] = p

    expected_names: set[str] = set(name_to_passenger.keys())
    seen_names: set[str] = set()

    for driver_id, assignments in llm_result.items():
        if not isinstance(assignments, list):
            violations.append(
                f"Driver '{driver_id}': expected a list of passenger assignments, "
                f"got {type(assignments).__name__}."
            )
            continue

        for entry in assignments:
            if not isinstance(entry, dict) or "name" not in entry or "location" not in entry:
                violations.append(
                    f"Driver '{driver_id}': malformed entry {entry!r}; "
                    "expected {'name': str, 'location': str}."
                )
                continue

            name = entry["name"]
            location = entry["location"]

            if not isinstance(name, str) or not isinstance(location, str):
                violations.append(
                    f"Driver '{driver_id}': entry has non-string name or location: {entry!r}."
                )
                continue

            if name in seen_names:
                violations.append(f"Passenger '{name}' is assigned to multiple drivers.")
            seen_names.add(name)

            passenger = name_to_passenger.get(name)
            if passenger is None:
                violations.append(
                    f"Passenger '{name}' assigned to {driver_id} is not in the input list."
                )
                continue

            allowed = _allowed_pickup_values(passenger)
            normalized = _normalize_location(location)
            short = normalized.split()[0] if normalized else normalized
            if normalized not in allowed and short not in allowed:
                violations.append(
                    f"Passenger '{name}' was assigned to location '{location}', "
                    f"but their allowed pickup location is '{passenger.pickup_location}'."
                )

    missing = expected_names - seen_names
    if missing:
        violations.append(
            "Passengers missing from the assignment: " + ", ".join(sorted(missing)) + "."
        )

    for driver_id, assignments in llm_result.items():
        if not isinstance(assignments, list):
            continue
        match = _DRIVER_ID_RE.match(driver_id)
        if not match:
            # Model chose an off-protocol driver label. Flag it; the bot expects DriverN.
            violations.append(
                f"Driver label '{driver_id}' does not match the expected pattern 'DriverN'."
            )
            continue
        idx = int(match.group(1))
        if idx < 0 or idx >= len(driver_capacity_list):
            violations.append(
                f"Driver '{driver_id}' is not one of the provided drivers "
                f"(expected Driver0..Driver{len(driver_capacity_list) - 1})."
            )
            continue
        if len(assignments) > driver_capacity_list[idx]:
            violations.append(
                f"Driver '{driver_id}' has {len(assignments)} passengers, "
                f"exceeding capacity {driver_capacity_list[idx]}."
            )

    return violations


def format_repair_instructions(
    previous_output: str,
    violations: list[str],
) -> str:
    """Build the repair instructions appended to the original prompt on a retry.

    The repair message restates the previous (invalid) output, lists the
    specific violations, and asks the model to produce a corrected assignment.
    Keeping the original prompt intact (rather than crafting a new one from
    scratch) preserves all the constraints and the distance table.
    """
    bullets = "\n".join(f"- {v}" for v in violations)
    return (
        "\n\nYour previous answer was:\n"
        f"{previous_output}\n\n"
        "That answer violated the following constraints:\n"
        f"{bullets}\n\n"
        "Produce a corrected JSON object that satisfies all constraints. "
        "Do not repeat the previous mistakes. Return only the JSON."
    )
