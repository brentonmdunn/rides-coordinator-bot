"""Unit tests for bot.jobs.ask_rides (wildcard dates, message builders)."""

from unittest.mock import patch

from bot.jobs.ask_rides import (
    WILDCARD_DATES,
    _is_wildcard_date,
    _make_friday_msg,
    _make_sunday_msg,
    _make_wednesday_msg,
)


class TestIsWildcardDate:
    """Tests for _is_wildcard_date."""

    def test_builds_correct_key(self):
        """The function appends /<yy> to the input and checks WILDCARD_DATES."""
        # "99/99" won't be in WILDCARD_DATES regardless of year
        assert _is_wildcard_date("99/99") is False

    def test_known_wildcard_date_for_2025(self):
        """6/20 should be wildcard only when year is 2025."""
        # If current year is 2025, 6/20 matches. Otherwise it won't.
        from datetime import datetime

        from bot.utils.time_helpers import LA_TZ

        year_suffix = datetime.now(tz=LA_TZ).strftime("%y")
        expected = f"6/20/{year_suffix}" in WILDCARD_DATES
        assert _is_wildcard_date("6/20") is expected


class TestWildcardDates:
    """Tests for the WILDCARD_DATES constant."""

    def test_all_have_year_suffix(self):
        for d in WILDCARD_DATES:
            parts = d.split("/")
            assert len(parts) == 3, f"Date {d} does not have m/d/yy format"

    def test_year_suffix_is_two_digits(self):
        for d in WILDCARD_DATES:
            year = d.split("/")[2]
            assert len(year) == 2
            assert year.isdigit()

    def test_not_empty(self):
        assert len(WILDCARD_DATES) > 0


class TestMakeWednesdayMsg:
    """Tests for _make_wednesday_msg."""

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/22")
    def test_returns_message(self, mock_date, mock_wildcard):
        result = _make_wednesday_msg()
        assert result is not None
        assert "Wednesday" in result
        assert "4/22" in result
        assert "Bible study" in result

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/20")
    def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert _make_wednesday_msg() is None


class TestMakeFridayMsg:
    """Tests for _make_friday_msg."""

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/24")
    def test_returns_message(self, mock_date, mock_wildcard):
        result = _make_friday_msg()
        assert result is not None
        assert "Friday" in result
        assert "4/24" in result
        assert "fellowship" in result

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/27")
    def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert _make_friday_msg() is None


class TestMakeSundayMsg:
    """Tests for _make_sunday_msg."""

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    def test_returns_message(self, mock_date, mock_wildcard):
        result = _make_sunday_msg()
        assert result is not None
        assert "Sunday" in result
        assert "4/26" in result

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/29")
    def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert _make_sunday_msg() is None

    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    def test_message_contains_emojis(self, mock_date, mock_wildcard):
        result = _make_sunday_msg()
        assert "🍔" in result
        assert "🏠" in result
