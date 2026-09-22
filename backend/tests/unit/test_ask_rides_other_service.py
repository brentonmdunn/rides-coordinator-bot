"""Unit tests for ridebot/services/ask_rides_other_service.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.services.ask_rides_other_service import AskRidesOtherService, _reset_cooldowns
from ridebot.services.pickup_info_service import Person
from ridebot.utils.ask_rides_defaults import DEFAULT_TEMPLATES
from ridebot.utils.time_helpers import LA_TZ
from shared.core.enums import AskRidesMessageType

FIND_MEMBER = "ridebot.services.ask_rides_other_service.PickupInfoService.find_member"
SEND_ERROR = "ridebot.services.ask_rides_other_service.send_error_to_discord"


def _la(*args) -> datetime:
    """Build a tz-aware LA datetime, correctly localized (pytz needs `.localize`)."""
    return LA_TZ.localize(datetime(*args))


@pytest.fixture(autouse=True)
def _reset():
    """Ensure the module-level cooldown dict doesn't leak between tests."""
    _reset_cooldowns()
    yield
    _reset_cooldowns()


def _make_person(**overrides) -> Person:
    defaults = {
        "id": 1,
        "name": "Alice",
        "discord_username": "alice",
        "discord_user_id": "123",
        "year": "2nd",
        "location": "Sixth",
        "phone": None,
        "updated_at": None,
    }
    defaults.update(overrides)
    return Person(**defaults)


class TestIsCurrent:
    def test_sunday_2359_previous_week_is_stale(self):
        # Monday Sept 15 2025 00:00 LA is this week's start; Sunday 23:59 the
        # week before (Sept 14, 23:59) is stale.
        now = _la(2025, 9, 15, 12, 0)
        message_created_at = _la(2025, 9, 14, 23, 59)
        assert AskRidesOtherService.is_current(message_created_at, now=now) is False

    def test_monday_0000_is_current(self):
        now = _la(2025, 9, 15, 12, 0)
        message_created_at = _la(2025, 9, 15, 0, 0)
        assert AskRidesOtherService.is_current(message_created_at, now=now) is True

    def test_utc_aware_value_near_la_midnight(self):
        # Monday 00:00 LA (PDT, UTC-7) is Monday 07:00 UTC.
        now = _la(2025, 9, 15, 12, 0)
        message_created_at = datetime(2025, 9, 15, 7, 0, tzinfo=UTC)
        assert AskRidesOtherService.is_current(message_created_at, now=now) is True

        just_before = datetime(2025, 9, 15, 6, 59, tzinfo=UTC)
        assert AskRidesOtherService.is_current(just_before, now=now) is False


class TestCooldown:
    def test_no_submission_not_on_cooldown(self):
        assert AskRidesOtherService.is_on_cooldown(1, now=1000.0) is False

    def test_within_window_is_on_cooldown(self):
        AskRidesOtherService.record_submission(1, now=1000.0)
        assert AskRidesOtherService.is_on_cooldown(1, now=1030.0) is True

    def test_after_window_not_on_cooldown(self):
        AskRidesOtherService.record_submission(1, now=1000.0)
        assert AskRidesOtherService.is_on_cooldown(1, now=1061.0) is False


class TestBuildCoordinatorMessage:
    def _build(self, **overrides):
        defaults = {
            "user_id": 42,
            "username": "bob",
            "announcement_title": "Rides to Sunday Service",
            "jump_url": "https://discord.com/channels/1/2/3",
            "text": "I need a ride",
            "person": _make_person(),
            "lookup_failed": False,
        }
        defaults.update(overrides)
        return AskRidesOtherService.build_coordinator_message(**defaults)

    def test_registered_person(self):
        msg = self._build()
        lines = msg.split("\n")
        assert lines[0] == (
            "✳️ **Something else** from <@42> (`@bob`) on "
            "**Rides to Sunday Service** · [Jump to message](https://discord.com/channels/1/2/3)"
        )
        assert lines[1] == "📍 Alice · Sixth · 2nd year"
        assert lines[2] == "> I need a ride"

    def test_person_missing_location_and_year(self):
        msg = self._build(person=_make_person(location=None, year=None))
        lines = msg.split("\n")
        assert lines[1] == "📍 Alice · no pickup spot · year unknown year"

    def test_unregistered_person(self):
        msg = self._build(person=None, lookup_failed=False)
        lines = msg.split("\n")
        assert lines[1] == "⚠️ Not registered for pickup info"

    def test_lookup_failed(self):
        msg = self._build(person=None, lookup_failed=True)
        lines = msg.split("\n")
        assert lines[1] == "⚠️ Couldn't load pickup info"

    def test_multiline_text_with_blank_line_is_quoted(self):
        msg = self._build(text="  line 1\n\nline 2  ")
        lines = msg.split("\n")
        assert lines[2] == "> line 1"
        assert lines[3] == ">"
        assert lines[4] == "> line 2"


def _make_user(user_id=42, username="bob"):
    user = MagicMock()
    user.id = user_id
    user.name = username
    return user


def _make_announcement(title="Custom Title", message_id=999):
    announcement = MagicMock(spec=discord.Message)
    announcement.id = message_id
    announcement.jump_url = "https://discord.com/channels/1/2/3"
    embed = MagicMock()
    embed.title = title
    announcement.embeds = [embed]
    return announcement


def _make_client(channel=None):
    client = MagicMock()
    client.get_channel = MagicMock(return_value=channel)
    return client


class TestSubmit:
    @pytest.mark.asyncio
    async def test_success_uses_no_mentions_and_records_cooldown(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        client = _make_client(channel)
        user = _make_user()
        announcement = _make_announcement()

        with patch(FIND_MEMBER, new=AsyncMock(return_value=_make_person())):
            result = await AskRidesOtherService.submit(
                client=client,
                user=user,
                message_type=AskRidesMessageType.SUNDAY_SERVICE,
                announcement=announcement,
                text="I need a ride",
            )

        assert result is True
        channel.send.assert_awaited_once()
        _, kwargs = channel.send.call_args
        sent_mentions = kwargs["allowed_mentions"]
        assert sent_mentions.everyone is False
        assert sent_mentions.users is False
        assert sent_mentions.roles is False
        assert kwargs["suppress_embeds"] is True
        assert AskRidesOtherService.is_on_cooldown(user.id) is True

    @pytest.mark.asyncio
    async def test_missing_channel_returns_false(self):
        client = _make_client(None)
        user = _make_user()
        announcement = _make_announcement()

        with (
            patch(FIND_MEMBER, new=AsyncMock(return_value=_make_person())),
            patch(SEND_ERROR, new=AsyncMock()) as send_error,
        ):
            result = await AskRidesOtherService.submit(
                client=client,
                user=user,
                message_type=AskRidesMessageType.SUNDAY_SERVICE,
                announcement=announcement,
                text="I need a ride",
            )

        assert result is False
        send_error.assert_awaited_once()
        assert AskRidesOtherService.is_on_cooldown(user.id) is False

    @pytest.mark.asyncio
    async def test_send_exception_returns_false(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock(side_effect=RuntimeError("boom"))
        client = _make_client(channel)
        user = _make_user()
        announcement = _make_announcement()

        with (
            patch(FIND_MEMBER, new=AsyncMock(return_value=_make_person())),
            patch(SEND_ERROR, new=AsyncMock()) as send_error,
        ):
            result = await AskRidesOtherService.submit(
                client=client,
                user=user,
                message_type=AskRidesMessageType.SUNDAY_SERVICE,
                announcement=announcement,
                text="I need a ride",
            )

        assert result is False
        send_error.assert_awaited_once()
        assert AskRidesOtherService.is_on_cooldown(user.id) is False

    @pytest.mark.asyncio
    async def test_lookup_exception_still_sends_with_couldnt_load_line(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        client = _make_client(channel)
        user = _make_user()
        announcement = _make_announcement()

        with patch(FIND_MEMBER, new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await AskRidesOtherService.submit(
                client=client,
                user=user,
                message_type=AskRidesMessageType.SUNDAY_SERVICE,
                announcement=announcement,
                text="I need a ride",
            )

        assert result is True
        channel.send.assert_awaited_once()
        (msg,), _ = channel.send.call_args
        assert "Couldn't load pickup info" in msg

    @pytest.mark.asyncio
    async def test_no_embed_falls_back_to_default_title(self):
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()
        client = _make_client(channel)
        user = _make_user()
        announcement = MagicMock(spec=discord.Message)
        announcement.id = 999
        announcement.jump_url = "https://discord.com/channels/1/2/3"
        announcement.embeds = []

        with patch(FIND_MEMBER, new=AsyncMock(return_value=_make_person())):
            await AskRidesOtherService.submit(
                client=client,
                user=user,
                message_type=AskRidesMessageType.SUNDAY_SERVICE,
                announcement=announcement,
                text="I need a ride",
            )

        (msg,), _ = channel.send.call_args
        expected_title = DEFAULT_TEMPLATES[AskRidesMessageType.SUNDAY_SERVICE].title
        assert expected_title in msg
