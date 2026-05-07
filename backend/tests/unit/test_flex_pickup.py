"""Tests for the Marshall flex-pickup behavior.

Marshall residents can be picked up at either MARSHALL (upper campus) or
GEISEL_LOOP (near Warren/Innovation). The pipeline supports this via
``Passenger.alt_pickup_locations``; several call-sites need to cooperate:

- ``llm_input_pickups`` renders flex passengers in a dedicated section.
- ``validate_assignment`` accepts any location from the allowed set.
- ``resolve_chosen_pickup`` maps the LLM's chosen string back to one of the
  allowed ``PickupLocations`` enum values.
- ``create_output`` honors the chosen pickup rather than the primary.
"""

from datetime import time

import pytest

from bot.core.enums import CampusLivingLocations, PickupLocations
from bot.core.schemas import Identity, Passenger
from bot.services.assignment_validator import validate_assignment
from bot.services.group_rides_service import living_to_alt_pickups
from bot.services.ride_grouping import (
    PassengersByLocation,
    create_output,
    llm_input_pickups,
    resolve_chosen_pickup,
)


def _marshall(name: str) -> Passenger:
    """Build a Marshall resident with the Geisel Loop alternative."""
    return Passenger(
        identity=Identity(name=name, username=name),
        living_location=CampusLivingLocations.MARSHALL,
        pickup_location=PickupLocations.MARSHALL,
        alt_pickup_locations=[PickupLocations.GEISEL_LOOP],
    )


def _innovation(name: str) -> Passenger:
    """Build an Innovation-pickup passenger (no alternatives)."""
    return Passenger(
        identity=Identity(name=name, username=name),
        living_location=CampusLivingLocations.PCE,
        pickup_location=PickupLocations.INNOVATION,
    )


def _muir(name: str) -> Passenger:
    """Build a Muir passenger (no alternatives)."""
    return Passenger(
        identity=Identity(name=name, username=name),
        living_location=CampusLivingLocations.MUIR,
        pickup_location=PickupLocations.MUIR,
    )


@pytest.fixture
def mixed_passengers() -> PassengersByLocation:
    """Two Marshall flex passengers + one Muir + one Innovation."""
    return {
        PickupLocations.MARSHALL: [_marshall("erin"), _marshall("frank")],
        PickupLocations.MUIR: [_muir("grace")],
        PickupLocations.INNOVATION: [_innovation("henry")],
    }


class TestMarshallFlexMapping:
    """Ensure the static config correctly exposes Marshall's alternatives."""

    def test_marshall_has_geisel_alternative(self):
        """Only Marshall has an alternative right now."""
        assert living_to_alt_pickups[CampusLivingLocations.MARSHALL] == [
            PickupLocations.GEISEL_LOOP
        ]

    def test_non_marshall_has_no_alternatives(self):
        """Residents of neighborhoods not in the map have no flex options."""
        assert CampusLivingLocations.MUIR not in living_to_alt_pickups
        assert CampusLivingLocations.RITA not in living_to_alt_pickups


class TestFlexInPromptInput:
    """llm_input_pickups should split fixed and flex passengers."""

    def test_fixed_section_omits_flex(self, mixed_passengers):
        """Marshall (flex) should not appear in the location-keyed section."""
        rendered = llm_input_pickups(mixed_passengers)
        # Muir and Innovation are fixed; they should appear in the usual format.
        assert "Muir tennis courts: grace" in rendered
        assert "Innovation: henry" in rendered
        # Marshall is flex, so its primary-location line should be empty / absent.
        assert "Marshall uppers: erin" not in rendered
        assert "Marshall uppers: erin, frank" not in rendered

    def test_flex_section_lists_each_passenger(self, mixed_passengers):
        """Each flex passenger is listed individually with the allowed tag."""
        rendered = llm_input_pickups(mixed_passengers)
        assert "Flex pickups" in rendered
        assert "erin [allowed: Marshall uppers, Geisel Loop]" in rendered
        assert "frank [allowed: Marshall uppers, Geisel Loop]" in rendered


class TestValidatorAcceptsFlex:
    """The semantic validator should accept any allowed pickup for flex riders."""

    def test_all_marshall_upper_accepted(self, mixed_passengers):
        """Assigning both flex passengers to Marshall upper is valid."""
        result = {
            "Driver0": [
                {"name": "erin", "location": "Marshall uppers"},
                {"name": "frank", "location": "Marshall uppers"},
                {"name": "grace", "location": "Muir tennis courts"},
                {"name": "henry", "location": "Innovation"},
            ],
        }
        assert validate_assignment(result, mixed_passengers, [4]) == []

    def test_all_marshall_geisel_accepted(self, mixed_passengers):
        """Assigning both flex passengers to Geisel Loop is valid."""
        result = {
            "Driver0": [
                {"name": "erin", "location": "Geisel Loop"},
                {"name": "frank", "location": "Geisel Loop"},
                {"name": "grace", "location": "Muir"},
                {"name": "henry", "location": "Innovation"},
            ],
        }
        assert validate_assignment(result, mixed_passengers, [4]) == []

    def test_split_between_marshall_and_geisel_accepted(self, mixed_passengers):
        """Splitting flex passengers across allowed locations is valid."""
        result = {
            "Driver0": [
                {"name": "erin", "location": "Marshall uppers"},
                {"name": "grace", "location": "Muir"},
            ],
            "Driver1": [
                {"name": "frank", "location": "Geisel Loop"},
                {"name": "henry", "location": "Innovation"},
            ],
        }
        assert validate_assignment(result, mixed_passengers, [2, 2]) == []

    def test_disallowed_location_still_rejected(self, mixed_passengers):
        """A flex passenger cannot be sent to a location outside their allowed set."""
        result = {
            "Driver0": [
                {"name": "erin", "location": "Rita"},
                {"name": "frank", "location": "Marshall"},
                {"name": "grace", "location": "Muir"},
                {"name": "henry", "location": "Innovation"},
            ],
        }
        violations = validate_assignment(result, mixed_passengers, [4])
        assert any("erin" in v and "Rita" in v for v in violations)


class TestResolveChosenPickup:
    """resolve_chosen_pickup picks the right enum for the LLM's string."""

    def test_primary_location_returned_for_fixed_passenger(self):
        muir = _muir("x")
        assert resolve_chosen_pickup("Muir", muir) == PickupLocations.MUIR
        assert resolve_chosen_pickup("Muir tennis courts", muir) == PickupLocations.MUIR

    def test_flex_passenger_resolves_to_alternative(self):
        erin = _marshall("erin")
        assert resolve_chosen_pickup("Geisel Loop", erin) == PickupLocations.GEISEL_LOOP
        assert resolve_chosen_pickup("GeiselLoop", erin) == PickupLocations.GEISEL_LOOP
        assert resolve_chosen_pickup("Marshall uppers", erin) == PickupLocations.MARSHALL
        assert resolve_chosen_pickup("Marshall", erin) == PickupLocations.MARSHALL

    def test_unrecognized_falls_back_to_primary(self):
        erin = _marshall("erin")
        assert resolve_chosen_pickup("Some Random Spot", erin) == PickupLocations.MARSHALL


class TestCreateOutputUsesChosenLocation:
    """create_output should place Marshall riders at their *chosen* pickup."""

    def test_marshall_rider_at_geisel_loop_renders_as_geisel(self, mixed_passengers):
        """When the LLM assigns Erin to Geisel Loop, the output string says Geisel Loop."""
        llm_result = {
            "Driver0": [
                {"name": "erin", "location": "Geisel Loop"},
                {"name": "henry", "location": "Innovation"},
            ],
        }
        output_list = create_output(
            llm_result=llm_result,
            locations_people=mixed_passengers,
            end_leave_time=time(hour=10, minute=0),
            off_campus={},
        )
        joined = "\n".join(output_list)
        assert "Geisel Loop" in joined
        # The original Marshall primary must NOT appear for Erin's driver.
        assert "Marshall uppers" not in joined
