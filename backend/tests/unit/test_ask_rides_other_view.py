"""Unit tests for ridebot/views/ask_rides_other.py."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.cogs.reactions import Reactions
from ridebot.utils.constants import ask_rides_other_custom_id
from ridebot.views.ask_rides_other import (
    _COOLDOWN,
    _FAILED,
    _SENT,
    _STALE,
    _UNAVAILABLE,
    AskRidesOtherModal,
    AskRidesOtherView,
)
from shared.core.enums import AskRidesMessageType

IS_ENABLED = "ridebot.views.ask_rides_other.AskRidesOtherService.is_enabled"
IS_CURRENT = "ridebot.views.ask_rides_other.AskRidesOtherService.is_current"
IS_ON_COOLDOWN = "ridebot.views.ask_rides_other.AskRidesOtherService.is_on_cooldown"
SUBMIT = "ridebot.views.ask_rides_other.AskRidesOtherService.submit"
SEND_ERROR = "ridebot.views.ask_rides_other.send_error_to_discord"


def _make_interaction(*, message=None, user_id=123, username="alice"):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.name = username
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()
    interaction.message = message
    interaction.client = MagicMock()
    return interaction


def _make_announcement(created_at=None):
    announcement = MagicMock()
    announcement.created_at = created_at or datetime.now(tz=UTC)
    return announcement


@pytest.mark.asyncio
@pytest.mark.parametrize("message_type", list(AskRidesMessageType))
async def test_view_has_one_button_with_custom_id(message_type):
    view = AskRidesOtherView(message_type)

    assert view.timeout is None
    assert len(view.children) == 1
    button = view.children[0]
    assert button.custom_id == ask_rides_other_custom_id(message_type)


@pytest.mark.asyncio
async def test_on_click_disabled_refuses():
    view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
    interaction = _make_interaction(message=_make_announcement())

    with patch(IS_ENABLED, new=AsyncMock(return_value=False)):
        await view.children[0].callback(interaction)

    interaction.response.send_message.assert_awaited_once_with(_UNAVAILABLE, ephemeral=True)
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_on_click_no_message_is_stale():
    view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
    interaction = _make_interaction(message=None)

    with patch(IS_ENABLED, new=AsyncMock(return_value=True)):
        await view._on_click(interaction)

    interaction.response.send_message.assert_awaited_once_with(_STALE, ephemeral=True)
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_on_click_stale_message_refuses():
    view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
    interaction = _make_interaction(message=_make_announcement())

    with (
        patch(IS_ENABLED, new=AsyncMock(return_value=True)),
        patch(IS_CURRENT, return_value=False),
    ):
        await view._on_click(interaction)

    interaction.response.send_message.assert_awaited_once_with(_STALE, ephemeral=True)
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_on_click_cooldown_refuses():
    view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
    interaction = _make_interaction(message=_make_announcement())

    with (
        patch(IS_ENABLED, new=AsyncMock(return_value=True)),
        patch(IS_CURRENT, return_value=True),
        patch(IS_ON_COOLDOWN, return_value=True),
    ):
        await view._on_click(interaction)

    interaction.response.send_message.assert_awaited_once_with(_COOLDOWN, ephemeral=True)
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_on_click_happy_path_sends_modal():
    view = AskRidesOtherView(AskRidesMessageType.SUNDAY_SERVICE)
    announcement = _make_announcement()
    interaction = _make_interaction(message=announcement)

    with (
        patch(IS_ENABLED, new=AsyncMock(return_value=True)),
        patch(IS_CURRENT, return_value=True),
        patch(IS_ON_COOLDOWN, return_value=False),
    ):
        await view._on_click(interaction)

    interaction.response.send_modal.assert_awaited_once()
    modal = interaction.response.send_modal.call_args.args[0]
    assert isinstance(modal, AskRidesOtherModal)
    assert modal.message_type == AskRidesMessageType.SUNDAY_SERVICE
    assert modal.announcement is announcement


@pytest.mark.asyncio
async def test_on_submit_success_sends_sent_message():
    announcement = _make_announcement()
    modal = AskRidesOtherModal(AskRidesMessageType.SUNDAY_SERVICE, announcement)
    modal.text_input._value = "I need a ride"
    interaction = _make_interaction(message=announcement)

    with patch(SUBMIT, new=AsyncMock(return_value=True)) as mock_submit:
        await modal.on_submit(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    mock_submit.assert_awaited_once_with(
        client=interaction.client,
        user=interaction.user,
        message_type=AskRidesMessageType.SUNDAY_SERVICE,
        announcement=announcement,
        text="I need a ride",
    )
    interaction.followup.send.assert_awaited_once_with(_SENT, ephemeral=True)


@pytest.mark.asyncio
async def test_on_submit_failure_sends_failed_message():
    announcement = _make_announcement()
    modal = AskRidesOtherModal(AskRidesMessageType.SUNDAY_SERVICE, announcement)
    modal.text_input._value = "I need a ride"
    interaction = _make_interaction(message=announcement)

    with patch(SUBMIT, new=AsyncMock(return_value=False)):
        await modal.on_submit(interaction)

    interaction.followup.send.assert_awaited_once_with(_FAILED, ephemeral=True)


@pytest.mark.asyncio
async def test_on_error_sends_failed_via_followup_when_response_done():
    announcement = _make_announcement()
    modal = AskRidesOtherModal(AskRidesMessageType.SUNDAY_SERVICE, announcement)
    interaction = _make_interaction(message=announcement)
    interaction.response.is_done = MagicMock(return_value=True)

    with patch(SEND_ERROR, new=AsyncMock()) as mock_send_error:
        await modal.on_error(interaction, RuntimeError("boom"))

    mock_send_error.assert_awaited_once()
    interaction.followup.send.assert_awaited_once_with(_FAILED, ephemeral=True)
    interaction.response.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_on_error_sends_failed_via_response_when_not_done():
    announcement = _make_announcement()
    modal = AskRidesOtherModal(AskRidesMessageType.SUNDAY_SERVICE, announcement)
    interaction = _make_interaction(message=announcement)
    interaction.response.is_done = MagicMock(return_value=False)

    with patch(SEND_ERROR, new=AsyncMock()):
        await modal.on_error(interaction, RuntimeError("boom"))

    interaction.response.send_message.assert_awaited_once_with(_FAILED, ephemeral=True)
    interaction.followup.send.assert_not_called()


def _make_cog():
    bot = MagicMock()
    bot.get_cog.return_value = None
    bot.add_view = MagicMock()
    logging_service = AsyncMock()
    ride_request_service = AsyncMock()
    return Reactions(bot, logging_service, ride_request_service), bot


@pytest.mark.asyncio
async def test_cog_load_registers_a_view_per_message_type():
    cog, bot = _make_cog()

    await cog.cog_load()

    assert bot.add_view.call_count == 1 + len(AskRidesMessageType)
