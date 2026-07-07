"""Unit tests for bot.jobs.ask_rides (wildcard dates, message builders)."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.core.enums import AskRidesMessageType, EmbedColorChoice
from bot.jobs.ask_rides import (
    WILDCARD_DATES,
    _is_wildcard_date,
    _make_friday_msg,
    _make_sunday_msg,
    _make_sunday_msg_class,
    _make_wednesday_msg,
)
from bot.services.ask_rides_messages_service import EffectiveTemplate


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


def _default_template() -> EffectiveTemplate:
    return EffectiveTemplate(
        title="Rides to Wednesday Fellowship",
        body="React to this message if you need a ride for Wednesday college fellowship {date} (leave between 7 and 7:10pm)!",
        color=EmbedColorChoice.TEAL.value,
        is_customized=False,
    )


def _custom_template() -> EffectiveTemplate:
    return EffectiveTemplate(
        title="Custom Wednesday Title",
        body="Custom body with {date}!",
        color=EmbedColorChoice.RED.value,
        is_customized=True,
    )


class TestMakeWednesdayMsg:
    """Tests for _make_wednesday_msg."""

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/22")
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_default_message(self, mock_get_template, mock_date, mock_wildcard):
        mock_get_template.return_value = _default_template()
        result = await _make_wednesday_msg()
        assert result is not None
        title, body, _color, _reactions = result
        assert title == "Rides to Wednesday Fellowship"
        assert "4/22" in body
        assert "college fellowship" in body
        mock_get_template.assert_awaited_once_with(AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/22")
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_customized_template_when_present(
        self, mock_get_template, mock_date, mock_wildcard
    ):
        mock_get_template.return_value = _custom_template()
        result = await _make_wednesday_msg()
        assert result is not None
        title, body, _color, _reactions = result
        assert title == "Custom Wednesday Title"
        assert body == "Custom body with 4/22!"

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/20")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert await _make_wednesday_msg() is None


class TestMakeFridayMsg:
    """Tests for _make_friday_msg."""

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/24")
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_message(self, mock_get_template, mock_date, mock_wildcard):
        from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.FRIDAY_FELLOWSHIP]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await _make_friday_msg()
        assert result is not None
        title, body, _color, _reactions = result
        assert "Friday" in title
        assert "4/24" in body
        assert "fellowship" in body

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/27")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert await _make_friday_msg() is None


class TestMakeSundayMsg:
    """Tests for _make_sunday_msg."""

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "bot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_message(self, mock_get_template, mock_ping, mock_date, mock_wildcard):
        from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await _make_sunday_msg()
        assert result is not None
        title, body, _color, _reactions = result
        assert "Sunday" in title
        assert "4/26" in body

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="6/29")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard):
        assert await _make_sunday_msg() is None

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "bot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_message_contains_emojis(
        self, mock_get_template, mock_ping, mock_date, mock_wildcard
    ):
        from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await _make_sunday_msg()
        assert result is not None
        _title, body, _color, _reactions = result
        assert "🍔" in body
        assert "🏠" in body
        assert "@coordinator" in body


class TestMakeSundayMsgClass:
    """Tests for _make_sunday_msg_class."""

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/27")
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_customized_template_when_present(self, mock_get_template, mock_date):
        mock_get_template.return_value = EffectiveTemplate(
            title="Custom Class Title",
            body="Custom class body {date}",
            color=EmbedColorChoice.PURPLE.value,
            is_customized=True,
        )
        result = await _make_sunday_msg_class()
        assert result is not None
        title, body, _color, _reactions = result
        assert title == "Custom Class Title"
        assert body == "Custom class body 4/27"

    @pytest.mark.asyncio
    @patch("bot.jobs.ask_rides.get_next_date_str", return_value="4/27")
    @patch(
        "bot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_default_when_not_customized(self, mock_get_template, mock_date):
        from bot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_CLASS]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await _make_sunday_msg_class()
        assert result is not None
        title, body, _color, _reactions = result
        assert title == "Rides to Bible Theology Class"
        assert "4/27" in body
