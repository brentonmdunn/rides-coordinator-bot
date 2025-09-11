import pytest
from app.cogs.group_rides import parse_numbers, llm_input_drivers

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
        assert llm_input_drivers([4, 2, 5]) == "Driver0 has capacity 4, Driver1 has capacity 2, Driver2 has capacity 5"

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
        assert llm_input_drivers([1, 2.5, "3"]) == "Driver0 has capacity 1, Driver1 has capacity 2.5, Driver2 has capacity 3"