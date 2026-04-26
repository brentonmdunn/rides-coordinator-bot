"""Tests for the semantic assignment validator."""

import pytest

from bot.core.enums import CampusLivingLocations, PickupLocations
from bot.core.schemas import Identity, Passenger
from bot.services.assignment_validator import format_repair_instructions, validate_assignment
from bot.services.ride_grouping import PassengersByLocation


@pytest.fixture
def sample_passengers() -> PassengersByLocation:
    """Two passengers at Sixth, one at ERC."""
    return {
        PickupLocations.SIXTH: [
            Passenger(
                identity=Identity(name="alice"),
                living_location=CampusLivingLocations.SIXTH,
                pickup_location=PickupLocations.SIXTH,
            ),
            Passenger(
                identity=Identity(name="bob"),
                living_location=CampusLivingLocations.SIXTH,
                pickup_location=PickupLocations.SIXTH,
            ),
        ],
        PickupLocations.ERC: [
            Passenger(
                identity=Identity(name="carol"),
                living_location=CampusLivingLocations.ERC,
                pickup_location=PickupLocations.ERC,
            ),
        ],
    }


class TestValidateAssignment:
    """Cases that exercise validate_assignment."""

    def test_valid_assignment_returns_no_violations(self, sample_passengers):
        """A complete, legal assignment should produce an empty violation list."""
        result = {
            "Driver0": [
                {"name": "alice", "location": str(PickupLocations.SIXTH)},
                {"name": "bob", "location": str(PickupLocations.SIXTH)},
                {"name": "carol", "location": str(PickupLocations.ERC)},
            ],
        }
        assert validate_assignment(result, sample_passengers, [4]) == []

    def test_lenient_short_location_form_is_accepted(self, sample_passengers):
        """The LLM may use short labels like 'Sixth' instead of 'Sixth loop'."""
        result = {
            "Driver0": [
                {"name": "alice", "location": "Sixth"},
                {"name": "bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        assert validate_assignment(result, sample_passengers, [4]) == []

    def test_missing_passenger_is_flagged(self, sample_passengers):
        """Missing passengers should be reported in the violations list."""
        result = {"Driver0": [{"name": "alice", "location": "Sixth"}]}
        violations = validate_assignment(result, sample_passengers, [4])
        assert any("missing" in v.lower() for v in violations)
        assert any("bob" in v for v in violations)
        assert any("carol" in v for v in violations)

    def test_phantom_name_is_flagged(self, sample_passengers):
        """A name not in the input should produce a violation."""
        result = {
            "Driver0": [
                {"name": "alice", "location": "Sixth"},
                {"name": "bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
                {"name": "dan", "location": "Sixth"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [4])
        assert any("dan" in v for v in violations)

    def test_duplicate_passenger_is_flagged(self, sample_passengers):
        """A passenger appearing on two drivers should produce a violation."""
        result = {
            "Driver0": [
                {"name": "alice", "location": "Sixth"},
                {"name": "bob", "location": "Sixth"},
            ],
            "Driver1": [
                {"name": "alice", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [4, 4])
        assert any("multiple drivers" in v for v in violations)

    def test_capacity_violation_is_flagged(self, sample_passengers):
        """Driver with too many passengers should be flagged."""
        result = {
            "Driver0": [
                {"name": "alice", "location": "Sixth"},
                {"name": "bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [2])
        assert any("exceeding capacity" in v for v in violations)

    def test_wrong_location_is_flagged(self, sample_passengers):
        """A passenger assigned to someone else's pickup location should be flagged."""
        result = {
            "Driver0": [
                {"name": "alice", "location": "Rita"},
                {"name": "bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [4])
        assert any("alice" in v and "Rita" in v for v in violations)

    def test_comma_in_name_is_not_a_validator_concern(self, sample_passengers):
        """The validator doesn't enforce the no-comma rule; that's handled separately."""
        # "alice, bob" becomes a phantom name ("alice, bob" is not in inputs).
        result = {
            "Driver0": [
                {"name": "alice, bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [4])
        # Expect phantom + missing (alice, bob).
        assert any("alice, bob" in v for v in violations)
        assert any("missing" in v.lower() for v in violations)

    def test_bad_driver_label_is_flagged(self, sample_passengers):
        """Labels that don't match DriverN are flagged."""
        result = {
            "BobsCar": [
                {"name": "alice", "location": "Sixth"},
                {"name": "bob", "location": "Sixth"},
                {"name": "carol", "location": "ERC"},
            ],
        }
        violations = validate_assignment(result, sample_passengers, [4])
        assert any("BobsCar" in v for v in violations)


class TestFormatRepairInstructions:
    """Cases that exercise format_repair_instructions."""

    def test_includes_previous_output_and_violations(self):
        """The repair instruction block should include both the previous response and bullets."""
        instructions = format_repair_instructions(
            previous_output='{"Driver0": []}',
            violations=["Missing: alice", "Capacity exceeded"],
        )
        assert "Driver0" in instructions
        assert "Missing: alice" in instructions
        assert "Capacity exceeded" in instructions
        # The instruction should explicitly ask for a correction.
        assert "correct" in instructions.lower() or "corrected" in instructions.lower()
