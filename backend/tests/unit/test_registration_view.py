"""Unit tests for ridebot/views/registration.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.services.roster_service import Person
from ridebot.utils.custom_exceptions import RosterConflictError, RosterValidationError
from ridebot.views.registration import (
    _OTHER_LOCATION_VALUE,
    RegistrationModal,
    RegistrationView,
)
from shared.core.enums import FeatureFlagNames
from shared.repositories.feature_flags_repository import FeatureFlagsRepository


@pytest.fixture(autouse=True)
def _enable_flags():
    """Enable both RideBot's kill switch and NEW_RIDES_MSG via the cache."""
    FeatureFlagsRepository._cache[FeatureFlagNames.RIDEBOT] = True
    FeatureFlagsRepository._cache[FeatureFlagNames.NEW_RIDES_MSG] = True
    yield
    FeatureFlagsRepository._cache.pop(FeatureFlagNames.RIDEBOT, None)
    FeatureFlagsRepository._cache.pop(FeatureFlagNames.NEW_RIDES_MSG, None)


def _make_person(**overrides) -> Person:
    defaults = {
        "id": 1,
        "name": "Alice",
        "discord_username": "alice",
        "discord_user_id": "123",
        "year": "2nd",
        "location": "Sixth",
        "updated_at": None,
    }
    defaults.update(overrides)
    return Person(**defaults)


def _make_interaction(user_id=123, username="alice", display_name="Alice"):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.name = username
    interaction.user.display_name = display_name
    interaction.response = AsyncMock()
    return interaction


# ---------------------------------------------------------------------------
# RegistrationView.register button callback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_sends_modal_when_flags_enabled():
    interaction = _make_interaction()
    view = RegistrationView()

    with patch(
        "ridebot.views.registration.RosterService.find_member", new=AsyncMock(return_value=None)
    ):
        await view.register.callback(interaction)

    interaction.response.send_modal.assert_awaited_once()
    sent_modal = interaction.response.send_modal.call_args.args[0]
    assert isinstance(sent_modal, RegistrationModal)


@pytest.mark.asyncio
async def test_register_refuses_ephemerally_when_kill_switch_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.RIDEBOT] = False
    interaction = _make_interaction()
    view = RegistrationView()

    await view.register.callback(interaction)

    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert "unavailable" in args[0].lower()
    assert kwargs.get("ephemeral") is True
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_register_refuses_ephemerally_when_new_rides_msg_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.NEW_RIDES_MSG] = False
    interaction = _make_interaction()
    view = RegistrationView()

    await view.register.callback(interaction)

    interaction.response.send_message.assert_awaited_once()
    interaction.response.send_modal.assert_not_called()


# ---------------------------------------------------------------------------
# RegistrationModal pre-fill
# ---------------------------------------------------------------------------


def _make_user(display_name="Bob"):
    user = MagicMock()
    user.display_name = display_name
    return user


@pytest.mark.asyncio
async def test_modal_prefills_from_existing_person():
    existing = _make_person(name="Alice", year="3rd", location="Muir")
    modal = RegistrationModal(existing, _make_user())

    assert modal.name_input.default == "Alice"
    year_default = next(o for o in modal.year_select.options if o.default)
    assert year_default.value == "3rd"
    location_default = next(o for o in modal.location_select.options if o.default)
    assert location_default.value == "Muir"


@pytest.mark.asyncio
async def test_modal_prefills_display_name_when_unregistered():
    modal = RegistrationModal(None, _make_user(display_name="Bob"))

    assert modal.name_input.default == "Bob"
    assert not any(o.default for o in modal.year_select.options)
    assert not any(o.default for o in modal.location_select.options)


@pytest.mark.asyncio
async def test_modal_prefills_off_campus_location_as_other():
    existing = _make_person(location="Costa Verde")
    modal = RegistrationModal(existing, _make_user())

    location_default = next(o for o in modal.location_select.options if o.default)
    assert location_default.value == _OTHER_LOCATION_VALUE
    assert modal.other_location_input.default == "Costa Verde"


# ---------------------------------------------------------------------------
# RegistrationModal.on_submit
# ---------------------------------------------------------------------------


def _submitted_modal(
    existing=None, name="Alice", year="2nd", location="Sixth", other_location=None
):
    modal = RegistrationModal(existing, _make_user())
    modal.name_input._value = name
    modal.year_select._values = [year]
    modal.location_select._values = [location]
    if other_location is not None:
        modal.other_location_input._value = other_location
    return modal


@pytest.mark.asyncio
async def test_on_submit_success_created():
    modal = _submitted_modal()
    interaction = _make_interaction()
    person = _make_person(name="Alice", year="2nd", location="Sixth")

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord",
        new=AsyncMock(return_value=(person, True)),
    ):
        await modal.on_submit(interaction)

    interaction.response.send_message.assert_awaited_once()
    args, kwargs = interaction.response.send_message.call_args
    assert args[0] == "✅ Registered **Alice**: Sixth, 2nd year"
    assert kwargs.get("ephemeral") is not True


@pytest.mark.asyncio
async def test_on_submit_success_updated():
    modal = _submitted_modal()
    interaction = _make_interaction()
    person = _make_person(name="Alice", year="2nd", location="Sixth")

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord",
        new=AsyncMock(return_value=(person, False)),
    ):
        await modal.on_submit(interaction)

    args, _ = interaction.response.send_message.call_args
    assert args[0] == "Updated: ✅ Registered **Alice**: Sixth, 2nd year"


@pytest.mark.asyncio
async def test_on_submit_other_uses_typed_location():
    modal = _submitted_modal(location=_OTHER_LOCATION_VALUE, other_location="  Costa Verde  ")
    interaction = _make_interaction()
    person = _make_person(name="Alice", year="2nd", location="Costa Verde")

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord",
        new=AsyncMock(return_value=(person, True)),
    ) as mock_register:
        await modal.on_submit(interaction)

    assert mock_register.call_args.kwargs["location"] == "Costa Verde"
    args, _ = interaction.response.send_message.call_args
    assert args[0] == "✅ Registered **Alice**: Costa Verde, 2nd year"


@pytest.mark.asyncio
async def test_on_submit_other_without_text_asks_again():
    modal = _submitted_modal(location=_OTHER_LOCATION_VALUE, other_location="   ")
    interaction = _make_interaction()

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord", new=AsyncMock()
    ) as mock_register:
        await modal.on_submit(interaction)

    mock_register.assert_not_awaited()
    args, kwargs = interaction.response.send_message.call_args
    assert "type where you live" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_on_submit_validation_error_is_ephemeral():
    modal = _submitted_modal()
    interaction = _make_interaction()

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord",
        new=AsyncMock(side_effect=RosterValidationError("bad name")),
    ):
        await modal.on_submit(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert "Couldn't register: bad name" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_on_submit_conflict_error_is_ephemeral():
    modal = _submitted_modal()
    interaction = _make_interaction()

    with patch(
        "ridebot.views.registration.RosterService.register_from_discord",
        new=AsyncMock(side_effect=RosterConflictError("taken")),
    ):
        await modal.on_submit(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert "Couldn't register: taken" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_on_submit_unexpected_error_reports_and_replies_ephemeral():
    modal = _submitted_modal()
    interaction = _make_interaction()

    with (
        patch(
            "ridebot.views.registration.RosterService.register_from_discord",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ),
        patch(
            "ridebot.views.registration.send_error_to_discord", new=AsyncMock()
        ) as mock_send_error,
    ):
        await modal.on_submit(interaction)

    mock_send_error.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
