from datetime import time
from typing import cast
from unittest.mock import patch

import pytest

from bot.core.enums import CampusLivingLocations
from bot.core.schemas import Identity, Passenger
from bot.services.ride_grouping import (
    PassengersByLocation,
    calculate_pickup_time,
    count_tuples,
    create_output,
    find_passenger,
    is_enough_capacity,
    llm_input_drivers,
    llm_input_pickups,
    parse_numbers,
)
from tests.unit.routing_fixtures import make_seed_context

SEED_CTX = make_seed_context()


@pytest.fixture
def sample_passengers() -> dict[str, Passenger]:
    """Provides a dictionary of sample Passenger objects for reuse in tests."""
    return {
        "alice": Passenger(
            identity=Identity(name="Alice", username="alice"),
            living_location=CampusLivingLocations.SIXTH,
            pickup_location="Sixth loop",
        ),
        "bob": Passenger(
            identity=Identity(name="Bob", username="bob"),
            living_location=CampusLivingLocations.ERC,
            pickup_location="ERC across from bamboo",
        ),
        "charlie": Passenger(
            identity=Identity(name="Charlie", username="charlie"),
            living_location=CampusLivingLocations.SIXTH,
            pickup_location="Sixth loop",
        ),
    }


@pytest.fixture
def sample_locations_people(sample_passengers: dict[str, Passenger]) -> PassengersByLocation:
    """Provides a sample PassengersByLocation dictionary, which maps locations to passengers."""
    return {
        "Sixth loop": [sample_passengers["alice"], sample_passengers["charlie"]],
        "ERC across from bamboo": [sample_passengers["bob"]],
        "Marshall uppers": [],  # A location with no one waiting
    }


class TestParseNumbers:
    """Test suite for the parse_numbers function."""

    def test_with_spaces(self):
        """Test parsing a string of numbers separated by spaces."""
        s = "1 2 3 4 5"
        expected = [1, 2, 3, 4, 5]
        assert parse_numbers(s) == expected

    def test_without_spaces(self):
        """Test parsing a string of numbers with no spaces."""
        s = "67890"
        expected = [6, 7, 8, 9, 0]
        assert parse_numbers(s) == expected

    def test_mixed_spaces(self):
        """Test parsing a string with a mix of spaces."""
        s = "1 23  4 5"
        expected = [1, 2, 3, 4, 5]
        assert parse_numbers(s) == expected

    def test_empty_string(self):
        """Test parsing an empty string."""
        s = ""
        expected = []
        assert parse_numbers(s) == expected

    def test_single_number(self):
        """Test parsing a string with a single digit."""
        s = "7"
        expected = [7]
        assert parse_numbers(s) == expected

    def test_invalid_character_raises_error(self):
        """Test that a ValueError is raised for non-digit characters."""
        with pytest.raises(ValueError):
            parse_numbers("1 2 a 4")


class TestLlmInputDrivers:
    """Test suite for the llm_input_drivers function."""

    def test_empty_list(self):
        """Test with an empty list of capacities."""
        assert llm_input_drivers([]) == ""

    def test_single_driver(self):
        """Test with a single driver capacity."""
        assert llm_input_drivers([4]) == "Driver0 has capacity 4"

    def test_multiple_drivers(self):
        """Test with a list of multiple driver capacities."""
        assert (
            llm_input_drivers([4, 2, 5])
            == "Driver0 has capacity 4, Driver1 has capacity 2, Driver2 has capacity 5"
        )

    def test_zero_capacity(self):
        """Test with a driver having zero capacity."""
        assert llm_input_drivers([0, 1]) == "Driver0 has capacity 0, Driver1 has capacity 1"

    def test_negative_capacity(self):
        """Test with a negative capacity to ensure it is handled as a string."""
        assert llm_input_drivers([-1]) == "Driver0 has capacity -1"

    def test_list_with_different_data_types(self):
        """Test with a list containing different data types."""
        # The function `llm_input_drivers` expects a list of integers.
        # Python's f-string will convert other types to strings.
        assert (
            llm_input_drivers(cast(list[int], [1, 2.5, "3"]))  # intentionally wrong types
            == "Driver0 has capacity 1, Driver1 has capacity 2.5, Driver2 has capacity 3"
        )


class TestFindPassenger:
    """Tests for the `find_passenger` function."""

    def test_find_passenger_success(
        self, sample_locations_people: PassengersByLocation, sample_passengers: dict[str, Passenger]
    ):
        """Should return the correct Passenger object when the person is at the specified location."""
        found_passenger = find_passenger(sample_locations_people, "Alice", "Sixth loop")
        assert found_passenger is not None
        assert found_passenger == sample_passengers["alice"]

    def test_find_passenger_at_wrong_location(self, sample_locations_people: PassengersByLocation):
        """Should return None if the person exists but is not at the specified location."""
        assert find_passenger(sample_locations_people, "Bob", "Sixth loop") is None

    def test_find_passenger_nonexistent_person(self, sample_locations_people: PassengersByLocation):
        """Should return None if the person's name does not exist."""
        assert find_passenger(sample_locations_people, "Zoe", "Sixth loop") is None

    def test_find_passenger_nonexistent_location(
        self, sample_locations_people: PassengersByLocation
    ):
        """Should return None if the location key does not exist in the dictionary."""
        assert find_passenger(sample_locations_people, "Alice", "Warren Equality Ln") is None

    def test_find_passenger_in_empty_location_list(
        self, sample_locations_people: PassengersByLocation
    ):
        """Should return None when searching in a location that has an empty list of passengers."""
        assert find_passenger(sample_locations_people, "Alice", "Marshall uppers") is None

    def test_find_passenger_with_empty_data(self):
        """Should return None when the main dictionary of locations is empty."""
        assert find_passenger({}, "Alice", "Sixth loop") is None


class TestCountTuples:
    """Tests for the `count_tuples` function."""

    def test_count_with_multiple_items(self, sample_locations_people: PassengersByLocation):
        """Should correctly count the total number of passengers across all locations."""
        # Alice, Charlie, and Bob = 3
        assert count_tuples(sample_locations_people) == 3

    def test_count_with_some_empty_lists(self, sample_passengers: dict[str, Passenger]):
        """Should correctly count, ignoring empty lists."""
        data: PassengersByLocation = {
            "Sixth loop": [sample_passengers["alice"]],
            "ERC across from bamboo": [],
            "Rita": [],
        }
        assert count_tuples(data) == 1

    def test_count_with_empty_dict(self):
        """Should return 0 for an empty dictionary."""
        assert count_tuples({}) == 0


class TestIsEnoughCapacity:
    """Tests for the `is_enough_capacity` function."""

    def test_capacity_is_enough(self, sample_locations_people: PassengersByLocation):
        """Should return True when total driver capacity is greater than the number of riders."""
        driver_capacity = [4]  # 4 seats for 3 riders
        assert is_enough_capacity(driver_capacity, sample_locations_people) is True

    def test_capacity_is_exact(self, sample_locations_people: PassengersByLocation):
        """Should return True when total driver capacity exactly matches the number of riders."""
        driver_capacity = [1, 1, 1]  # 3 seats for 3 riders
        assert is_enough_capacity(driver_capacity, sample_locations_people) is True

    def test_capacity_is_not_enough(self, sample_locations_people: PassengersByLocation):
        """Should return False when total driver capacity is less than the number of riders."""
        driver_capacity = [2]  # 2 seats for 3 riders
        assert is_enough_capacity(driver_capacity, sample_locations_people) is False

    def test_no_riders(self):
        """Should return True if there are no riders, as 0 capacity is sufficient."""
        assert is_enough_capacity([0], {}) is True
        assert is_enough_capacity([], {}) is True

    def test_no_drivers(self, sample_locations_people: PassengersByLocation):
        """Should return False if there are riders but no drivers."""
        assert is_enough_capacity([], sample_locations_people) is False


class TestCalculatePickupTime:
    """Tests for the `calculate_pickup_time` function."""

    # Create passenger objects specifically for route calculation testing
    p_muir = Passenger(
        identity=Identity(name="M", username="m"),
        living_location=CampusLivingLocations.MUIR,
        pickup_location="Muir tennis courts",
    )
    p_warren = Passenger(
        identity=Identity(name="W", username="w"),
        living_location=CampusLivingLocations.WARREN,
        pickup_location="Warren Equality Ln",
    )

    # This sample represents a route built in reverse pickup order.
    # The last pickup is at Warren, the one before that is at Muir.
    sample_route_so_far = [[p_warren]]  # noqa

    def test_simple_calculation(self):
        """Should correctly calculate a new pickup time by subtracting travel and adjustment time."""
        # Warren -> Innovation is 1 minute in the seed graph; use adjustment of 2.
        ctx = make_seed_context(pickup_adjustment=2)

        # Calculate the pickup time for Innovation, given the Warren pickup is at 16:30.
        # The function logic accesses the route from the end using the offset.
        # len(sample_route_so_far) = 1. offset = 1. Index = 1 - 1 = 0.
        # So it correctly queries the travel time from Warren to Innovation.
        new_time = calculate_pickup_time(
            curr_leave_time=time(16, 30),
            grouped_by_location=self.sample_route_so_far,
            location="Innovation",
            offset=1,
            routing=ctx,
        )

        # 16:30 minus (1 travel + 2 adjustment) = 16:27
        assert new_time == time(16, 27)


class TestLlmInputPickups:
    """Tests for the `llm_input_pickups` function."""

    def test_multiple_locations_and_passengers(self, sample_locations_people: PassengersByLocation):
        """Should generate a correctly formatted string for a typical passenger dictionary."""
        # Create a dictionary without the empty Marshall location for a clean expected string
        data = {k: v for k, v in sample_locations_people.items() if v}
        expected = "Sixth loop: Alice, Charlie\nERC across from bamboo: Bob\n"
        assert llm_input_pickups(data) == expected

    def test_location_with_empty_passenger_list(self, sample_passengers: dict[str, Passenger]):
        """Should correctly format a string even with a location that has no passengers."""
        data: PassengersByLocation = {
            "Sixth loop": [sample_passengers["alice"]],
            "ERC across from bamboo": [],
        }
        expected = "Sixth loop: Alice\nERC across from bamboo: \n"
        assert llm_input_pickups(data) == expected

    def test_empty_dict(self):
        """Should return an empty string for an empty input dictionary."""
        assert llm_input_pickups({}) == ""


# ---------------------------------------------------------------------------
# Fixtures shared by create_output tests
# ---------------------------------------------------------------------------


@pytest.fixture
def alice():
    return Passenger(
        identity=Identity(name="Alice", username="alice"),
        living_location=CampusLivingLocations.SIXTH,
        pickup_location="Sixth loop",
    )


@pytest.fixture
def bob():
    return Passenger(
        identity=Identity(name="Bob", username="bob"),
        living_location=CampusLivingLocations.ERC,
        pickup_location="ERC across from bamboo",
    )


@pytest.fixture
def charlie():
    return Passenger(
        identity=Identity(name="Charlie", username=None),
        living_location=CampusLivingLocations.MUIR,
        pickup_location="Muir tennis courts",
    )


class TestCreateOutput:
    """Tests for the `create_output` function (lines 165-246)."""

    @patch("bot.services.ride_grouping.calculate_pickup_time")
    def test_single_driver_single_location(self, mock_pickup_time, alice):
        """Single driver, single pickup location: no intermediate time calculation."""
        locations_people: PassengersByLocation = {
            "Sixth loop": [alice],
        }
        llm_result = {
            "Driver0": [{"name": "Alice", "location": "Sixth loop"}],
        }
        end_leave_time = time(17, 0)
        result = create_output(llm_result, locations_people, end_leave_time, {}, SEED_CTX)

        # First element is the summary, second is plain text, third is code block
        assert len(result) == 3
        assert "==== summary ====" in result[0]
        assert "================" in result[0]
        # calculate_pickup_time should NOT be called for the first (only) stop
        mock_pickup_time.assert_not_called()
        # Plain drive string present
        assert "drive:" in result[1]
        # Code block present
        assert "```" in result[2]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_single_driver_two_locations(self, mock_pickup_time, alice, bob):
        """Single driver picks up passengers at two different locations."""
        locations_people: PassengersByLocation = {
            "Sixth loop": [alice],
            "ERC across from bamboo": [bob],
        }
        # LLM assigns both to Driver0 but at different locations
        llm_result = {
            "Driver0": [
                {"name": "Alice", "location": "Sixth loop"},
                {"name": "Bob", "location": "ERC across from bamboo"},
            ],
        }
        end_leave_time = time(17, 0)
        result = create_output(llm_result, locations_people, end_leave_time, {}, SEED_CTX)

        # summary + 2 items per driver
        assert len(result) == 3
        # calculate_pickup_time called once for the second (earlier) stop
        mock_pickup_time.assert_called_once()
        # Both usernames in drive string
        assert "@alice" in result[1]
        assert "@bob" in result[1]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_two_drivers(self, mock_pickup_time, alice, bob):
        """Two drivers each picking up one passenger."""
        locations_people: PassengersByLocation = {
            "Sixth loop": [alice],
            "ERC across from bamboo": [bob],
        }
        llm_result = {
            "Driver0": [{"name": "Alice", "location": "Sixth loop"}],
            "Driver1": [{"name": "Bob", "location": "ERC across from bamboo"}],
        }
        end_leave_time = time(17, 0)
        result = create_output(llm_result, locations_people, end_leave_time, {}, SEED_CTX)

        # summary + 2 items per driver = 5 total
        assert len(result) == 5
        assert "==== summary ====" in result[0]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_map_url_included_when_present(self, mock_pickup_time, alice):
        """Seeded locations have coordinates, so a Google Maps link should appear."""
        locations_people: PassengersByLocation = {"Sixth loop": [alice]}
        llm_result = {"Driver0": [{"name": "Alice", "location": "Sixth loop"}]}
        result = create_output(llm_result, locations_people, time(17, 0), {}, SEED_CTX)

        assert "Google Maps" in result[1]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_unknown_passenger_skipped(self, mock_pickup_time, alice):
        """Passengers not in locations_people are skipped without raising an error."""
        locations_people: PassengersByLocation = {"Sixth loop": [alice]}
        llm_result = {
            "Driver0": [
                {"name": "Alice", "location": "Sixth loop"},
                {"name": "Ghost", "location": "ERC across from bamboo"},  # not in lookup
            ],
        }
        result = create_output(llm_result, locations_people, time(17, 0), {}, SEED_CTX)
        # Should still produce output without crashing; Ghost should be absent
        assert "Ghost" not in result[1]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_off_campus_passengers_in_summary(self, mock_pickup_time, alice):
        """Off-campus passengers should appear in the summary block."""
        locations_people: PassengersByLocation = {"Sixth loop": [alice]}
        llm_result = {"Driver0": [{"name": "Alice", "location": "Sixth loop"}]}
        off_campus = {"Some Place": [("Dave", "dave_username")]}
        result = create_output(llm_result, locations_people, time(17, 0), off_campus, SEED_CTX)

        assert "TODO: off campus" in result[0]
        assert "Dave" in result[0]
        assert "dave_username" in result[0]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_username_none_falls_back_to_name(self, mock_pickup_time, charlie):
        """When a passenger has no username, the name should appear in the drive string."""
        locations_people: PassengersByLocation = {"Muir tennis courts": [charlie]}
        llm_result = {"Driver0": [{"name": "Charlie", "location": "Muir tennis courts"}]}
        result = create_output(llm_result, locations_people, time(17, 0), {}, SEED_CTX)

        assert "Charlie" in result[1]

    @patch("bot.services.ride_grouping.calculate_pickup_time", return_value=time(16, 45))
    def test_same_location_passengers_grouped(self, mock_pickup_time, alice, charlie):
        """Two passengers at the same location should be grouped into one stop."""
        # Give charlie the same pickup location as alice
        charlie_sixth = Passenger(
            identity=Identity(name="Charlie", username="charlie"),
            living_location=CampusLivingLocations.SIXTH,
            pickup_location="Sixth loop",
        )
        locations_people: PassengersByLocation = {"Sixth loop": [alice, charlie_sixth]}
        llm_result = {
            "Driver0": [
                {"name": "Alice", "location": "Sixth loop"},
                {"name": "Charlie", "location": "Sixth loop"},
            ],
        }
        result = create_output(llm_result, locations_people, time(17, 0), {}, SEED_CTX)
        # No intermediate pickup time call since all at same location
        mock_pickup_time.assert_not_called()
        assert "@alice" in result[1]
        assert "@charlie" in result[1]
