"""Unit tests for ridebot.jobs.ask_rides (wildcard dates, message builders)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.jobs.ask_rides import (
    WILDCARD_DATES,
    _ask_rides_template,
    _is_wildcard_date,
    build_ask_rides_message,
)
from ridebot.services.ask_rides_messages_service import EffectiveTemplate
from shared.core.enums import AskRidesMessageType, EmbedColorChoice


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

        from ridebot.utils.time_helpers import LA_TZ

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


class TestBuildAskRidesMessageWednesday:
    """Tests for build_ask_rides_message with WEDNESDAY_FELLOWSHIP."""

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/22")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_default_message(
        self, mock_get_template, mock_date, mock_wildcard, mock_enabled
    ):
        mock_get_template.return_value = _default_template()
        result = await build_ask_rides_message(AskRidesMessageType.WEDNESDAY_FELLOWSHIP)
        assert result is not None
        embed, _reactions, view = result
        assert embed.title == "Rides to Wednesday Fellowship"
        assert "4/22" in (embed.description or "")
        assert "college fellowship" in (embed.description or "")
        assert view is None
        mock_get_template.assert_awaited_once_with(AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/22")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_customized_template_when_present(
        self, mock_get_template, mock_date, mock_wildcard, mock_enabled
    ):
        mock_get_template.return_value = _custom_template()
        result = await build_ask_rides_message(AskRidesMessageType.WEDNESDAY_FELLOWSHIP)
        assert result is not None
        embed, _reactions, _view = result
        assert embed.title == "Custom Wednesday Title"
        assert embed.description == "Custom body with 4/22!"

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="6/20")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard, mock_enabled):
        assert await build_ask_rides_message(AskRidesMessageType.WEDNESDAY_FELLOWSHIP) is None


class TestBuildAskRidesMessageFriday:
    """Tests for build_ask_rides_message with FRIDAY_FELLOWSHIP."""

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/24")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_message(self, mock_get_template, mock_date, mock_wildcard, mock_enabled):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.FRIDAY_FELLOWSHIP]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.FRIDAY_FELLOWSHIP)
        assert result is not None
        embed, _reactions, _view = result
        assert "Friday" in (embed.title or "")
        assert "4/24" in (embed.description or "")
        assert "fellowship" in (embed.description or "")

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="6/27")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard, mock_enabled):
        assert await build_ask_rides_message(AskRidesMessageType.FRIDAY_FELLOWSHIP) is None


class TestBuildAskRidesMessageSunday:
    """Tests for build_ask_rides_message with SUNDAY_SERVICE."""

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "ridebot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_returns_message(
        self, mock_get_template, mock_ping, mock_date, mock_wildcard, mock_enabled
    ):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_SERVICE)
        assert result is not None
        embed, _reactions, view = result
        assert "Sunday" in (embed.title or "")
        assert "4/26" in (embed.description or "")
        assert view is None

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="6/29")
    async def test_returns_none_for_wildcard(self, mock_date, mock_wildcard, mock_enabled):
        assert await build_ask_rides_message(AskRidesMessageType.SUNDAY_SERVICE) is None

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "ridebot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_message_contains_emojis_and_dm_fallback_when_disabled(
        self, mock_get_template, mock_ping, mock_date, mock_wildcard, mock_enabled
    ):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_SERVICE)
        assert result is not None
        embed, _reactions, _view = result
        body = embed.description or ""
        assert "🍔" in body
        assert "🏠" in body
        assert "@coordinator" in body
        assert "please DM @coordinator" in body

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=True,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "ridebot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_attaches_view_when_enabled(
        self, mock_get_template, mock_ping, mock_date, mock_wildcard, mock_enabled
    ):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES
        from ridebot.views.ask_rides_other import AskRidesOtherView

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_SERVICE)
        assert result is not None
        embed, _reactions, view = result
        assert isinstance(view, AskRidesOtherView)
        assert "tap **Something else** below" in (embed.description or "")

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=False)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/26")
    @patch(
        "ridebot.jobs.ask_rides.RideCoordinatorService.resolve_ping_text",
        new_callable=AsyncMock,
        return_value=("@coordinator", True),
    )
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_force_view_attaches_view_when_disabled(
        self, mock_get_template, mock_ping, mock_date, mock_wildcard, mock_enabled
    ):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES
        from ridebot.views.ask_rides_other import AskRidesOtherView

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_SERVICE, force_view=True)
        assert result is not None
        _embed, _reactions, view = result
        assert isinstance(view, AskRidesOtherView)


class TestBuildAskRidesMessageSundayClass:
    """Tests for build_ask_rides_message with SUNDAY_CLASS."""

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/27")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_customized_template_when_present(
        self, mock_get_template, mock_date, mock_enabled
    ):
        mock_get_template.return_value = EffectiveTemplate(
            title="Custom Class Title",
            body="Custom class body {date}",
            color=EmbedColorChoice.PURPLE.value,
            is_customized=True,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_CLASS)
        assert result is not None
        embed, _reactions, _view = result
        assert embed.title == "Custom Class Title"
        assert embed.description == "Custom class body 4/27"

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="4/27")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_uses_default_when_not_customized(
        self, mock_get_template, mock_date, mock_enabled
    ):
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_CLASS]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_CLASS)
        assert result is not None
        embed, _reactions, _view = result
        assert embed.title == "Rides to Bible Theology Class"
        assert "4/27" in (embed.description or "")

    @pytest.mark.asyncio
    @patch(
        "ridebot.jobs.ask_rides.AskRidesOtherService.is_enabled",
        new_callable=AsyncMock,
        return_value=False,
    )
    @patch("ridebot.jobs.ask_rides._is_wildcard_date", return_value=True)
    @patch("ridebot.jobs.ask_rides.get_next_date_str", return_value="6/29")
    @patch(
        "ridebot.jobs.ask_rides.AskRidesMessagesService.get_effective_template",
        new_callable=AsyncMock,
    )
    async def test_not_affected_by_wildcard_dates(
        self, mock_get_template, mock_date, mock_wildcard, mock_enabled
    ):
        """Sunday class isn't subject to the wildcard-date skip list, unlike the other types."""
        from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES

        template = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_CLASS]
        mock_get_template.return_value = EffectiveTemplate(
            title=template.title,
            body=template.body,
            color=template.color.value,
            is_customized=False,
        )
        result = await build_ask_rides_message(AskRidesMessageType.SUNDAY_CLASS)
        assert result is not None
        mock_wildcard.assert_not_called()


class TestAskRidesTemplateView:
    """Tests for _ask_rides_template passing the view only when present."""

    @pytest.mark.asyncio
    @patch("ridebot.jobs.ask_rides.build_ask_rides_message", new_callable=AsyncMock)
    async def test_sends_without_view_kwarg_value_when_none(self, mock_build):
        import discord

        embed = discord.Embed(title="t", description="d")
        mock_build.return_value = (embed, (), None)

        fake_channel = MagicMock()
        fake_channel.send = AsyncMock(return_value=MagicMock(id=1))
        fake_bot = MagicMock()
        fake_bot.get_channel.return_value = fake_channel

        # `isinstance(fake_channel, discord.TextChannel)` needs a real TextChannel
        # instance; patch the class itself to MagicMock so our MagicMock channel
        # passes the check.
        with (
            patch("ridebot.jobs.ask_rides.resolve_channel_id", return_value=123),
            patch("ridebot.jobs.ask_rides.discord.TextChannel", MagicMock),
        ):
            result = await _ask_rides_template(fake_bot, AskRidesMessageType.WEDNESDAY_FELLOWSHIP)

        assert result is not None
        fake_channel.send.assert_awaited_once()
        _args, kwargs = fake_channel.send.call_args
        assert kwargs["view"] is discord.utils.MISSING

    @pytest.mark.asyncio
    @patch("ridebot.jobs.ask_rides.build_ask_rides_message", new_callable=AsyncMock)
    async def test_sends_with_view_when_present(self, mock_build):
        import discord

        from ridebot.views.ask_rides_other import AskRidesOtherView

        embed = discord.Embed(title="t", description="d")
        with patch.object(AskRidesOtherView, "__init__", lambda self, message_type: None):
            view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
        mock_build.return_value = (embed, (), view)

        fake_channel = MagicMock()
        fake_channel.send = AsyncMock(return_value=MagicMock(id=1))
        fake_bot = MagicMock()
        fake_bot.get_channel.return_value = fake_channel

        with (
            patch("ridebot.jobs.ask_rides.resolve_channel_id", return_value=123),
            patch("ridebot.jobs.ask_rides.discord.TextChannel", MagicMock),
        ):
            result = await _ask_rides_template(fake_bot, AskRidesMessageType.SUNDAY_SERVICE)

        assert result is not None
        fake_channel.send.assert_awaited_once()
        _args, kwargs = fake_channel.send.call_args
        assert kwargs["view"] is view
