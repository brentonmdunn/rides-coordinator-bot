"""
Manual eval harness for the group rides LLM pipeline.

Runs a single scenario file end-to-end against the real pipeline so you can
inspect the rendered prompt, the raw Gemini output, the validator findings,
the per-driver total drive time, and the final Discord messages. There are
no gold/expected checks — the goal is to look at the output yourself and
decide whether the assignment is good.

Usage (run from ``backend/``):

    # Inspect the prompt only — no API key needed:
    uv run python -m evals.run_scenario evals/scenarios/basic.yaml --dry-run

    # Full run:
    uv run python -m evals.run_scenario evals/scenarios/basic.yaml

Scenario file format (YAML):

    name: "human-readable name"                  # optional
    notes: |                                     # optional free-text context
      Anything you want to remember later.
    drivers: [4, 4]                              # driver capacities
    event: sunday                                # optional: sunday|friday
    custom_prompt: "extra instructions..."       # optional
    passengers:
      - { name: alice,   living: Sixth }
      - { name: bob,     living: Marshall }      # flex: Marshall OR Geisel Loop
      - { name: carol,   living: Warren }
    expected:                                    # optional: gold-labelled answer
      cars:
        - passengers:
          - { name: alice, location: Sixth }
          - { name: bob,   location: Marshall }
        - passengers:
          - { name: carol, location: Warren }
      max_time_delta_minutes: 2                  # optional: tolerance for drive-time

Living values are matched case-insensitively against the
``CampusLivingLocations`` enum values ("Sixth", "Seventh", "Marshall",
"ERC", "Muir", "Eighth", "Revelle", "PCE", "PCW", "Rita", "Warren").

When ``expected`` is present, an extra ``GOLD COMPARISON`` section reports
partition, location, and order match plus the drive-time delta.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import time
from pathlib import Path
from typing import Any

import yaml

from bot.core.enums import CampusLivingLocations, PickupLocations
from bot.core.schemas import Identity, Passenger
from bot.services.assignment_validator import validate_assignment
from bot.services.group_rides_service import living_to_alt_pickups, living_to_pickup
from bot.services.ride_grouping import (
    PassengersByLocation,
    create_output,
    llm_input_drivers,
    llm_input_pickups,
    resolve_chosen_pickup,
)
from bot.utils.genai.prompt import (
    CUSTOM_INSTRUCTIONS,
    GROUP_RIDES_PROMPT,
    GROUP_RIDES_PROMPT_LEGACY,
    PROMPT_EPILOGUE,
)
from bot.utils.locations import (
    LOCATIONS_MATRIX,
    compute_all_pairs_shortest_paths,
    render_distance_markdown,
)
from evals.gold_compare import (
    compare_to_gold,
    format_gold_report,
    parse_expected,
)

DEFAULT_END_TIMES = {
    "sunday": time(hour=10, minute=10),
    "friday": time(hour=19, minute=10),
}


def _parse_living(raw: str) -> CampusLivingLocations:
    """Match a free-form living-location string against the enum, case-insensitively."""
    lowered = raw.strip().lower()
    for member in CampusLivingLocations:
        if member.value.lower() == lowered or member.name.lower() == lowered:
            return member
    raise ValueError(
        f"Unknown living location: {raw!r}. "
        f"Valid values: {', '.join(m.value for m in CampusLivingLocations)}"
    )


def build_scenario_inputs(
    scenario: dict[str, Any],
) -> tuple[PassengersByLocation, list[int]]:
    """
    Turn a scenario dict into the (passengers_by_location, driver_capacity_list) tuple.

    Mirrors ``GroupRidesService._split_on_off_campus`` but accepts structured
    YAML input instead of Discord reaction data.
    """
    passengers_by_location: PassengersByLocation = {}
    for entry in scenario.get("passengers", []):
        name = entry["name"]
        living = _parse_living(entry["living"])
        pickup = living_to_pickup[living]
        alts = living_to_alt_pickups.get(living, [])
        passenger = Passenger(
            identity=Identity(name=name, username=entry.get("username", name)),
            living_location=living,
            pickup_location=pickup,
            alt_pickup_locations=list(alts),
        )
        passengers_by_location.setdefault(pickup, []).append(passenger)

    drivers = list(scenario.get("drivers", []))
    if not drivers:
        raise ValueError("Scenario must define a non-empty 'drivers' list")
    return passengers_by_location, drivers


def render_prompt(
    pickups_str: str,
    drivers_str: str,
    custom_prompt: str | None,
    legacy: bool,
) -> str:
    """Compose the exact prompt string the LLM sees."""
    locations_md = render_distance_markdown(LOCATIONS_MATRIX)
    if legacy:
        template = GROUP_RIDES_PROMPT_LEGACY
    else:
        template = GROUP_RIDES_PROMPT
        if custom_prompt:
            template += CUSTOM_INSTRUCTIONS.format(custom_instructions=custom_prompt)
        template += PROMPT_EPILOGUE
    return template.format(
        pickups_str=pickups_str,
        drivers_str=drivers_str,
        locations_matrix=locations_md,
    )


def compute_per_driver_totals(
    llm_result: dict[str, list[dict[str, str]]],
    passengers_by_location: PassengersByLocation,
) -> tuple[dict[str, int], int]:
    """
    Compute total drive time (minutes) per driver and across all drivers.

    Walks ``START -> chosen_pickup_1 -> ... -> chosen_pickup_N -> END`` for
    each driver using the cached all-pairs shortest-path table. Consecutive
    same-location stops are collapsed. Passengers missing from the lookup
    map are skipped (they would already have produced a validator violation).
    """
    all_pairs = compute_all_pairs_shortest_paths(LOCATIONS_MATRIX)
    passenger_lookup = {
        p.identity.name: p for passengers in passengers_by_location.values() for p in passengers
    }

    per_driver: dict[str, int] = {}
    total = 0
    for driver_id, assignments in llm_result.items():
        if not isinstance(assignments, list):
            continue
        stops: list[PickupLocations] = []
        for obj in assignments:
            passenger = passenger_lookup.get(obj.get("name", ""))
            if not passenger:
                continue
            chosen = resolve_chosen_pickup(obj.get("location", ""), passenger)
            if not stops or stops[-1] != chosen:
                stops.append(chosen)
        if not stops:
            continue

        driver_total = 0
        prev: PickupLocations | str = "START"
        for stop in stops:
            driver_total += all_pairs[prev][stop]
            prev = stop
        driver_total += all_pairs[prev]["END"]

        per_driver[driver_id] = driver_total
        total += driver_total

    return per_driver, total


def _banner(title: str) -> str:
    return f"\n{'=' * 70}\n{title}\n{'=' * 70}"


def _section(title: str) -> str:
    return f"\n-- {title} --"


def run(scenario_path: Path, dry_run: bool, legacy: bool) -> int:
    """Execute a single scenario file and print the inspection report."""
    scenario = yaml.safe_load(scenario_path.read_text())
    if not isinstance(scenario, dict):
        print(f"error: {scenario_path} must contain a YAML mapping", file=sys.stderr)
        return 2

    passengers_by_location, drivers = build_scenario_inputs(scenario)
    pickups_str = llm_input_pickups(passengers_by_location)
    drivers_str = llm_input_drivers(drivers)
    custom_prompt = scenario.get("custom_prompt")

    event = scenario.get("event", "sunday")
    end_leave_time = DEFAULT_END_TIMES.get(event, DEFAULT_END_TIMES["sunday"])

    prompt = render_prompt(pickups_str, drivers_str, custom_prompt, legacy)

    print(_banner(f"SCENARIO: {scenario.get('name', scenario_path.stem)}"))
    if scenario.get("notes"):
        print(scenario["notes"].rstrip())
    print(_section("INPUT"))
    print(f"drivers: {drivers}")
    print(f"passengers: {len(scenario.get('passengers', []))}")
    print(f"event: {event}  end_leave_time: {end_leave_time.strftime('%H:%M')}")

    print(_section("PROMPT"))
    print(prompt)

    if dry_run:
        print("\n(dry-run: skipping Gemini call)")
        return 0

    # Defer LLM imports so --dry-run works without GOOGLE_API_KEY.
    from bot.services.llm_service import LLMService

    llm_service = LLMService()
    try:
        llm_result = llm_service.generate_ride_groups(
            pickups_str,
            drivers_str,
            LOCATIONS_MATRIX,
            legacy_prompt=legacy,
            custom_prompt=custom_prompt,
            passengers_by_location=passengers_by_location,
            driver_capacity_list=drivers,
        )
    except Exception as exc:
        print(_section("LLM CALL FAILED"))
        print(f"{type(exc).__name__}: {exc}")
        return 1

    print(_section("RAW LLM OUTPUT"))
    print(json.dumps(llm_result, indent=2))

    if "error" in {k.lower() for k in llm_result}:
        print(_section("LLM REPORTED NO VALID ASSIGNMENT"))
        return 0

    violations = validate_assignment(llm_result, passengers_by_location, drivers)
    print(_section("VALIDATOR"))
    if violations:
        for v in violations:
            print(f"  x {v}")
    else:
        print("  (all checks passed)")

    per_driver, total = compute_per_driver_totals(llm_result, passengers_by_location)
    print(_section("DRIVE TIME (minutes, includes START->first and last->END)"))
    for driver_id, driver_total in per_driver.items():
        stops = len(llm_result.get(driver_id, []))
        print(f"  {driver_id}: {driver_total} min across {stops} passenger(s)")
    print(f"  total: {total} min")

    raw_expected = scenario.get("expected")
    if raw_expected is not None:
        try:
            expected_cars, max_delta = parse_expected(raw_expected)
        except ValueError as exc:
            print(_section("GOLD COMPARISON"))
            print(f"  (invalid 'expected' block: {exc})")
        else:
            comparison = compare_to_gold(
                llm_result,
                passengers_by_location,
                expected_cars,
                max_delta,
            )
            print(_section("GOLD COMPARISON"))
            for line in format_gold_report(comparison):
                print(line)

    print(_section("RENDERED DISCORD MESSAGES"))
    messages = create_output(
        llm_result=llm_result,
        locations_people=passengers_by_location,
        end_leave_time=end_leave_time,
        off_campus={},
    )
    for message in messages:
        print(message)

    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to :func:`run`."""
    parser = argparse.ArgumentParser(
        description="Run a group-rides LLM scenario and print the output for inspection.",
    )
    parser.add_argument("scenario", type=Path, help="Path to a scenario YAML file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the rendered prompt but skip the Gemini API call.",
    )
    parser.add_argument(
        "--legacy-prompt",
        action="store_true",
        help="Use GROUP_RIDES_PROMPT_LEGACY instead of the current prompt.",
    )
    args = parser.parse_args(argv)

    if not args.scenario.exists():
        parser.error(f"scenario file not found: {args.scenario}")

    return run(args.scenario, args.dry_run, args.legacy_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
