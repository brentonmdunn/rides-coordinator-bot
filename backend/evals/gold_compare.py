"""
Gold-dataset comparison for the group rides eval harness.

When a scenario YAML includes an ``expected`` block, :func:`compare_to_gold`
reports how closely the LLM's assignment matches the coordinator-approved
answer at three strictness levels:

1. **Partition** — does the actual assignment group passengers into the
   same cars as gold (driver labels ignored)?
2. **Location** — does every passenger's chosen pickup location equal the
   gold location? Compared with the same normalization used in the
   production ``resolve_chosen_pickup`` (accepts "Sixth" vs "Sixth loop",
   "GeiselLoop" vs "Geisel Loop", etc.).
3. **Order** — within each matched car, is the pickup order identical?

Plus a numeric **drive-time delta** between gold and actual.

This module is pure inspection logic: it builds a :class:`GoldComparison`
object and a ``list[str]`` of human-readable diff lines. It never exits
the process or mutates inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bot.core.enums import PickupLocations
from bot.services.ride_grouping import (
    PassengersByLocation,
    resolve_chosen_pickup,
)
from bot.utils.locations import (
    LOCATIONS_MATRIX,
    compute_all_pairs_shortest_paths,
)

_ALL_PICKUPS: list[PickupLocations] = list(PickupLocations)


def _norm_forms(raw: str) -> set[str]:
    """Return the set of forms a location string can be matched against."""
    full = " ".join(raw.lower().split())
    short = full.split()[0] if full else full
    compressed = full.replace(" ", "")
    return {full, short, compressed}


def parse_pickup_string(raw: str) -> PickupLocations:
    """
    Resolve an arbitrary human-typed location string to a ``PickupLocations`` enum.

    Accepts any of the forms the production pipeline accepts (full enum
    value, first-word short form, run-together spelling). Raises
    ``ValueError`` when no enum member matches so scenario-author typos
    fail loudly.
    """
    raw_forms = _norm_forms(raw)
    for candidate in _ALL_PICKUPS:
        if raw_forms & _norm_forms(str(candidate)):
            return candidate
    raise ValueError(
        f"Unknown pickup location in gold scenario: {raw!r}. "
        f"Valid values: {', '.join(p.value for p in _ALL_PICKUPS)}",
    )


@dataclass(frozen=True)
class ExpectedCar:
    """One gold-labelled car: ordered list of (passenger_name, chosen_location)."""

    stops: tuple[tuple[str, PickupLocations], ...]

    @property
    def passenger_set(self) -> frozenset[str]:
        """Set of passenger names riding in this car."""
        return frozenset(name for name, _ in self.stops)

    @property
    def pickup_order(self) -> tuple[PickupLocations, ...]:
        """Consecutive same-location stops collapsed, matching drive-time logic."""
        out: list[PickupLocations] = []
        for _, loc in self.stops:
            if not out or out[-1] != loc:
                out.append(loc)
        return tuple(out)


@dataclass
class GoldComparison:
    """Structured result of comparing an LLM assignment against gold."""

    partition_match: bool
    location_match: bool
    order_match: bool
    partition_diffs: list[str] = field(default_factory=list)
    location_diffs: list[str] = field(default_factory=list)
    order_diffs: list[str] = field(default_factory=list)
    gold_total_time: int = 0
    actual_total_time: int = 0
    max_time_delta_minutes: int | None = None

    @property
    def drive_time_delta(self) -> int:
        """Actual total drive time minus gold total drive time, in minutes."""
        return self.actual_total_time - self.gold_total_time

    @property
    def within_time_tolerance(self) -> bool:
        """True when the drive-time delta is within ``max_time_delta_minutes``."""
        if self.max_time_delta_minutes is None:
            return True
        return self.drive_time_delta <= self.max_time_delta_minutes


def parse_expected(raw_expected: dict[str, Any]) -> tuple[list[ExpectedCar], int | None]:
    """Validate and parse an ``expected`` YAML block into structured cars."""
    cars_raw = raw_expected.get("cars")
    if not isinstance(cars_raw, list) or not cars_raw:
        raise ValueError("'expected.cars' must be a non-empty list")

    parsed_cars: list[ExpectedCar] = []
    seen_names: set[str] = set()
    for idx, car in enumerate(cars_raw):
        if not isinstance(car, dict):
            raise ValueError(f"expected.cars[{idx}] must be a mapping")
        pax = car.get("passengers")
        if not isinstance(pax, list) or not pax:
            raise ValueError(f"expected.cars[{idx}].passengers must be a non-empty list")
        stops: list[tuple[str, PickupLocations]] = []
        for entry in pax:
            if not isinstance(entry, dict) or "name" not in entry or "location" not in entry:
                raise ValueError(
                    f"expected.cars[{idx}].passengers entries must have 'name' and 'location'",
                )
            name = str(entry["name"])
            if name in seen_names:
                raise ValueError(f"passenger {name!r} appears in more than one expected car")
            seen_names.add(name)
            stops.append((name, parse_pickup_string(str(entry["location"]))))
        parsed_cars.append(ExpectedCar(stops=tuple(stops)))

    max_delta = raw_expected.get("max_time_delta_minutes")
    if max_delta is not None and not isinstance(max_delta, int):
        raise ValueError("'expected.max_time_delta_minutes' must be an integer")

    return parsed_cars, max_delta


def _build_actual_cars(
    llm_result: dict[str, list[dict[str, str]]],
    passengers_by_location: PassengersByLocation,
) -> dict[str, ExpectedCar]:
    """Resolve an LLM output into ``{driver_id: ExpectedCar}`` (reusing the gold schema)."""
    passenger_lookup = {
        p.identity.name: p for passengers in passengers_by_location.values() for p in passengers
    }
    out: dict[str, ExpectedCar] = {}
    for driver_id, assignments in llm_result.items():
        if not isinstance(assignments, list):
            continue
        stops: list[tuple[str, PickupLocations]] = []
        for obj in assignments:
            if not isinstance(obj, dict):
                continue
            name = str(obj.get("name", ""))
            passenger = passenger_lookup.get(name)
            if passenger is None:
                continue
            chosen = resolve_chosen_pickup(str(obj.get("location", "")), passenger)
            stops.append((name, chosen))
        if stops:
            out[driver_id] = ExpectedCar(stops=tuple(stops))
    return out


def _drive_time(order: tuple[PickupLocations, ...]) -> int:
    if not order:
        return 0
    table = compute_all_pairs_shortest_paths(LOCATIONS_MATRIX)
    total = 0
    prev: PickupLocations | str = "START"
    for stop in order:
        total += table[prev][stop]
        prev = stop
    total += table[prev]["END"]
    return total


def compare_to_gold(
    llm_result: dict[str, list[dict[str, str]]],
    passengers_by_location: PassengersByLocation,
    expected_cars: list[ExpectedCar],
    max_time_delta_minutes: int | None,
) -> GoldComparison:
    """
    Compare an LLM assignment against a gold-labelled set of cars.

    Driver IDs are NOT matched — actual cars are matched to gold cars by
    passenger set, then location and order comparisons run within each
    matched pair.
    """
    actual_cars = _build_actual_cars(llm_result, passengers_by_location)
    actual_by_set: dict[frozenset[str], ExpectedCar] = {
        car.passenger_set: car for car in actual_cars.values()
    }
    gold_by_set: dict[frozenset[str], ExpectedCar] = {
        car.passenger_set: car for car in expected_cars
    }

    # --- Partition match --------------------------------------------------
    partition_diffs: list[str] = []
    partition_match = set(actual_by_set.keys()) == set(gold_by_set.keys())
    if not partition_match:
        gold_owner = {
            name: car.passenger_set for car in expected_cars for name in car.passenger_set
        }
        actual_owner = {
            name: car.passenger_set for car in actual_cars.values() for name in car.passenger_set
        }
        misplaced: list[str] = []
        for name, expected_set in gold_owner.items():
            actual_set = actual_owner.get(name)
            if actual_set is None:
                misplaced.append(f"{name}: missing from actual assignment")
            elif actual_set != expected_set:
                misplaced.append(
                    f"{name}: expected car {sorted(expected_set)}, got car {sorted(actual_set)}",
                )
        partition_diffs = misplaced

    # --- Location match ---------------------------------------------------
    location_diffs: list[str] = []
    gold_locs = {name: loc for car in expected_cars for name, loc in car.stops}
    actual_locs = {name: loc for car in actual_cars.values() for name, loc in car.stops}
    for name, expected_loc in gold_locs.items():
        actual_loc = actual_locs.get(name)
        if actual_loc is None:
            location_diffs.append(f"{name}: unassigned (expected {expected_loc.value!r})")
        elif actual_loc != expected_loc:
            location_diffs.append(
                f"{name}: expected {expected_loc.value!r}, got {actual_loc.value!r}",
            )
    location_match = not location_diffs

    # --- Order match ------------------------------------------------------
    # Only meaningful when partition matches; otherwise we'd be comparing
    # different sets of passengers.
    order_diffs: list[str] = []
    order_match = partition_match
    if partition_match:
        for key, gold_car in gold_by_set.items():
            actual_car = actual_by_set[key]
            if gold_car.pickup_order != actual_car.pickup_order:
                order_match = False
                order_diffs.append(
                    f"car {sorted(key)}: expected order "
                    f"{[p.value for p in gold_car.pickup_order]}, "
                    f"got {[p.value for p in actual_car.pickup_order]}",
                )

    # --- Drive times ------------------------------------------------------
    gold_total = sum(_drive_time(car.pickup_order) for car in expected_cars)
    actual_total = sum(_drive_time(car.pickup_order) for car in actual_cars.values())

    return GoldComparison(
        partition_match=partition_match,
        location_match=location_match,
        order_match=order_match,
        partition_diffs=partition_diffs,
        location_diffs=location_diffs,
        order_diffs=order_diffs,
        gold_total_time=gold_total,
        actual_total_time=actual_total,
        max_time_delta_minutes=max_time_delta_minutes,
    )


def format_gold_report(result: GoldComparison) -> list[str]:
    """Render a :class:`GoldComparison` as printable lines (no trailing newlines)."""

    def _status(ok: bool) -> str:
        return "PASS" if ok else "FAIL"

    lines: list[str] = []
    lines.append(f"partition: {_status(result.partition_match)}")
    for diff in result.partition_diffs:
        lines.append(f"  x {diff}")

    lines.append(f"locations: {_status(result.location_match)}")
    for diff in result.location_diffs:
        lines.append(f"  x {diff}")

    lines.append(f"order: {_status(result.order_match)}")
    for diff in result.order_diffs:
        lines.append(f"  x {diff}")

    delta = result.drive_time_delta
    sign = "+" if delta >= 0 else ""
    tolerance_note = ""
    if result.max_time_delta_minutes is not None:
        verdict = "within tolerance" if result.within_time_tolerance else "EXCEEDS tolerance"
        tolerance_note = f", tolerance +{result.max_time_delta_minutes} min ({verdict})"
    lines.append(
        f"drive time: gold={result.gold_total_time} min, "
        f"actual={result.actual_total_time} min (delta {sign}{delta} min{tolerance_note})",
    )
    return lines
