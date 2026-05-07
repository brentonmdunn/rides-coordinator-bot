"""Unit tests for ``evals.gold_compare``."""

from __future__ import annotations

import pytest

from bot.core.enums import CampusLivingLocations, PickupLocations
from bot.core.schemas import Identity, Passenger
from evals.gold_compare import (
    ExpectedCar,
    GoldComparison,
    compare_to_gold,
    format_gold_report,
    parse_expected,
    parse_pickup_string,
)


def _passenger(
    name: str,
    living: CampusLivingLocations,
    pickup: PickupLocations,
    alt: list[PickupLocations] | None = None,
) -> Passenger:
    return Passenger(
        identity=Identity(name=name, username=name),
        living_location=living,
        pickup_location=pickup,
        alt_pickup_locations=list(alt or []),
    )


class TestParsePickupString:
    def test_full_enum_value(self) -> None:
        assert parse_pickup_string("Sixth loop") is PickupLocations.SIXTH

    def test_short_word(self) -> None:
        assert parse_pickup_string("Sixth") is PickupLocations.SIXTH

    def test_geisel_loop_with_space(self) -> None:
        assert parse_pickup_string("Geisel Loop") is PickupLocations.GEISEL_LOOP

    def test_geisel_loop_run_together(self) -> None:
        assert parse_pickup_string("GeiselLoop") is PickupLocations.GEISEL_LOOP

    def test_geisel_short(self) -> None:
        assert parse_pickup_string("Geisel") is PickupLocations.GEISEL_LOOP

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown pickup"):
            parse_pickup_string("Narnia")


class TestParseExpected:
    def test_valid(self) -> None:
        cars, max_delta = parse_expected(
            {
                "cars": [
                    {"passengers": [{"name": "alice", "location": "Muir"}]},
                    {"passengers": [{"name": "bob", "location": "Warren"}]},
                ],
                "max_time_delta_minutes": 3,
            },
        )
        assert len(cars) == 2
        assert cars[0].passenger_set == frozenset({"alice"})
        assert cars[1].stops == (("bob", PickupLocations.WARREN_EQL),)
        assert max_delta == 3

    def test_missing_cars(self) -> None:
        with pytest.raises(ValueError, match="non-empty list"):
            parse_expected({})

    def test_duplicate_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="more than one expected car"):
            parse_expected(
                {
                    "cars": [
                        {"passengers": [{"name": "alice", "location": "Muir"}]},
                        {"passengers": [{"name": "alice", "location": "Warren"}]},
                    ],
                },
            )

    def test_bad_max_delta_type(self) -> None:
        with pytest.raises(ValueError, match="integer"):
            parse_expected(
                {
                    "cars": [{"passengers": [{"name": "a", "location": "Muir"}]}],
                    "max_time_delta_minutes": "soon",
                },
            )


class TestCompareToGold:
    @pytest.fixture
    def passengers_by_location(self) -> dict[PickupLocations, list[Passenger]]:
        return {
            PickupLocations.MUIR: [
                _passenger("alice", CampusLivingLocations.MUIR, PickupLocations.MUIR)
            ],
            PickupLocations.SIXTH: [
                _passenger("bob", CampusLivingLocations.SIXTH, PickupLocations.SIXTH)
            ],
            PickupLocations.MARSHALL: [
                _passenger(
                    "marsha",
                    CampusLivingLocations.MARSHALL,
                    PickupLocations.MARSHALL,
                    [PickupLocations.GEISEL_LOOP],
                ),
            ],
            PickupLocations.WARREN_EQL: [
                _passenger("wendy", CampusLivingLocations.WARREN, PickupLocations.WARREN_EQL),
            ],
        }

    def test_perfect_match(
        self, passengers_by_location: dict[PickupLocations, list[Passenger]]
    ) -> None:
        llm_result = {
            "Driver0": [
                {"name": "alice", "location": "Muir"},
                {"name": "bob", "location": "Sixth"},
                {"name": "marsha", "location": "Marshall"},
            ],
            "Driver1": [
                {"name": "wendy", "location": "Warren"},
            ],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(llm_result, passengers_by_location, expected, None)
        assert result.partition_match
        assert result.location_match
        assert result.order_match
        assert result.partition_diffs == []
        assert result.location_diffs == []
        assert result.order_diffs == []
        assert result.drive_time_delta == 0

    def test_driver_labels_can_be_swapped(
        self,
        passengers_by_location: dict[PickupLocations, list[Passenger]],
    ) -> None:
        # Same pairing as the gold, but with driver IDs swapped.
        llm_result = {
            "Driver0": [{"name": "wendy", "location": "Warren"}],
            "Driver1": [
                {"name": "alice", "location": "Muir"},
                {"name": "bob", "location": "Sixth"},
                {"name": "marsha", "location": "Marshall"},
            ],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(llm_result, passengers_by_location, expected, None)
        assert result.partition_match
        assert result.order_match

    def test_wrong_partition(
        self,
        passengers_by_location: dict[PickupLocations, list[Passenger]],
    ) -> None:
        llm_result = {
            "Driver0": [
                {"name": "alice", "location": "Muir"},
                {"name": "wendy", "location": "Warren"},  # mispaired
            ],
            "Driver1": [
                {"name": "bob", "location": "Sixth"},
                {"name": "marsha", "location": "Marshall"},
            ],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(llm_result, passengers_by_location, expected, None)
        assert not result.partition_match
        assert not result.order_match  # order undefined when partition fails
        assert any("alice" in d for d in result.partition_diffs)

    def test_flex_location_mismatch(
        self,
        passengers_by_location: dict[PickupLocations, list[Passenger]],
    ) -> None:
        # Same partition as gold but marsha was sent to Geisel Loop instead of
        # the expected Marshall uppers.
        llm_result = {
            "Driver0": [
                {"name": "alice", "location": "Muir"},
                {"name": "bob", "location": "Sixth"},
                {"name": "marsha", "location": "Geisel Loop"},
            ],
            "Driver1": [{"name": "wendy", "location": "Warren"}],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(llm_result, passengers_by_location, expected, None)
        assert result.partition_match
        assert not result.location_match
        assert any("marsha" in d and "Marshall" in d for d in result.location_diffs)

    def test_order_mismatch(
        self,
        passengers_by_location: dict[PickupLocations, list[Passenger]],
    ) -> None:
        llm_result = {
            "Driver0": [
                {"name": "bob", "location": "Sixth"},  # swapped order
                {"name": "alice", "location": "Muir"},
                {"name": "marsha", "location": "Marshall"},
            ],
            "Driver1": [{"name": "wendy", "location": "Warren"}],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(llm_result, passengers_by_location, expected, None)
        assert result.partition_match
        assert result.location_match
        assert not result.order_match
        assert result.order_diffs

    def test_drive_time_delta_and_tolerance(
        self,
        passengers_by_location: dict[PickupLocations, list[Passenger]],
    ) -> None:
        llm_result = {
            "Driver0": [
                {"name": "alice", "location": "Muir"},
                {"name": "bob", "location": "Sixth"},
                {"name": "marsha", "location": "Marshall"},
            ],
            "Driver1": [{"name": "wendy", "location": "Warren"}],
        }
        expected = [
            ExpectedCar(
                stops=(
                    ("alice", PickupLocations.MUIR),
                    ("bob", PickupLocations.SIXTH),
                    ("marsha", PickupLocations.MARSHALL),
                ),
            ),
            ExpectedCar(stops=(("wendy", PickupLocations.WARREN_EQL),)),
        ]
        result = compare_to_gold(
            llm_result, passengers_by_location, expected, max_time_delta_minutes=5
        )
        assert result.drive_time_delta == 0
        assert result.within_time_tolerance


class TestFormatGoldReport:
    def test_pass_report(self) -> None:
        result = GoldComparison(
            partition_match=True,
            location_match=True,
            order_match=True,
            gold_total_time=14,
            actual_total_time=14,
        )
        lines = format_gold_report(result)
        assert lines[0] == "partition: PASS"
        assert lines[1] == "locations: PASS"
        assert lines[2] == "order: PASS"
        assert lines[-1].startswith("drive time: gold=14 min")
        assert "delta +0 min" in lines[-1]

    def test_fail_report_with_diffs(self) -> None:
        result = GoldComparison(
            partition_match=True,
            location_match=False,
            order_match=True,
            location_diffs=["marsha: expected 'Marshall uppers', got 'Geisel Loop'"],
            gold_total_time=14,
            actual_total_time=16,
            max_time_delta_minutes=1,
        )
        lines = format_gold_report(result)
        assert "locations: FAIL" in lines
        assert any("marsha" in line for line in lines)
        assert "EXCEEDS tolerance" in lines[-1]
