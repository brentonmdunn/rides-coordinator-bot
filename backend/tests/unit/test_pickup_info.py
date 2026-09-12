"""Unit tests for ridebot/views/pickup_info.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ridebot.services.pickup_info_service import Person
from ridebot.services.pickup_locations_service import PickupSpot
from ridebot.utils.custom_exceptions import PickupInfoConflictError, PickupInfoValidationError
from ridebot.views.pickup_info import (
    _NEEDS_FOLLOWUP_VALUE,
    CampusPickupModal,
    OffCampusPickupModal,
    PickupInfoView,
    SdsuPickupModal,
)
from shared.core.enums import CampusLivingLocations, ChannelIds, ClassYear, FeatureFlagNames
from shared.repositories.feature_flags_repository import FeatureFlagsRepository

REGISTER = "ridebot.views.pickup_info.PickupInfoService.register_from_discord"
FIND_MEMBER = "ridebot.views.pickup_info.PickupInfoService.find_member"
PICKUP_SPOTS = "ridebot.views.pickup_info.PickupLocationsService.pickup_spots_for_living"


@pytest.fixture(autouse=True)
def _no_pickup_spots():
    """Keep tests off the real routing snapshot unless a test opts in to spots."""
    with patch(PICKUP_SPOTS, new=AsyncMock(return_value=[])):
        yield


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


def _make_user(display_name="Bob"):
    user = MagicMock()
    user.display_name = display_name
    return user


def _make_interaction(user_id=123, username="alice", display_name="Alice"):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.name = username
    interaction.user.display_name = display_name
    interaction.response = AsyncMock()
    interaction.channel_id = 555
    # Ride coordinators channel the notice is mirrored into.
    coordinators_channel = MagicMock(spec=discord.TextChannel)
    coordinators_channel.send = AsyncMock()
    interaction.client = MagicMock()
    interaction.client.get_channel = MagicMock(return_value=coordinators_channel)
    return interaction


def _coordinators_channel(interaction):
    """Return the channel mock that `_notify_ride_coordinators` posts into."""
    return interaction.client.get_channel.return_value


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("button_name", "expected_modal"),
    [
        ("on_campus", CampusPickupModal),
        ("off_campus", OffCampusPickupModal),
        ("sdsu", SdsuPickupModal),
    ],
)
@pytest.mark.asyncio
async def test_each_button_opens_its_own_modal(button_name, expected_modal):
    interaction = _make_interaction()
    view = PickupInfoView()

    with patch(FIND_MEMBER, new=AsyncMock(return_value=None)):
        await getattr(view, button_name).callback(interaction)

    interaction.response.send_modal.assert_awaited_once()
    assert isinstance(interaction.response.send_modal.call_args.args[0], expected_modal)


@pytest.mark.asyncio
async def test_buttons_have_distinct_custom_ids():
    view = PickupInfoView()
    custom_ids = [child.custom_id for child in view.children]

    assert len(custom_ids) == 3
    assert len(set(custom_ids)) == 3


@pytest.mark.asyncio
async def test_refuses_ephemerally_when_kill_switch_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.RIDEBOT] = False
    interaction = _make_interaction()

    await PickupInfoView().on_campus.callback(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert "ride coordinator" in args[0].lower()
    assert kwargs.get("ephemeral") is True
    interaction.response.send_modal.assert_not_called()


@pytest.mark.asyncio
async def test_refuses_ephemerally_when_new_rides_msg_disabled():
    FeatureFlagsRepository._cache[FeatureFlagNames.NEW_RIDES_MSG] = False
    interaction = _make_interaction()

    await PickupInfoView().off_campus.callback(interaction)

    interaction.response.send_message.assert_awaited_once()
    interaction.response.send_modal.assert_not_called()


# ---------------------------------------------------------------------------
# Modal construction and pre-fill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_campus_modal_appends_followup_option_outside_the_enum():
    """The catch-all is a UI affordance only; it must never be a living location."""
    modal = CampusPickupModal(None, _make_user())
    values = [option.value for option in modal.location_select.options]
    campus_values = {location.value for location in CampusLivingLocations}

    assert values[-1] == _NEEDS_FOLLOWUP_VALUE
    assert _NEEDS_FOLLOWUP_VALUE not in campus_values
    # SDSU has its own button, so it is not offered in the on-campus list.
    assert CampusLivingLocations.SDSU.value not in values
    assert set(values[:-1]) == campus_values - {CampusLivingLocations.SDSU.value}


@pytest.mark.asyncio
async def test_campus_modal_prefills_existing_campus_area():
    modal = CampusPickupModal(_make_person(name="Alice", year="3rd", location="Muir"), _make_user())

    assert modal.name_input.default == "Alice"
    assert next(o for o in modal.year_select.options if o.default).value == "3rd"
    assert next(o for o in modal.location_select.options if o.default).value == "Muir"


@pytest.mark.asyncio
async def test_campus_modal_has_no_default_for_off_campus_person():
    modal = CampusPickupModal(_make_person(location="Costa Verde"), _make_user())

    assert not any(o.default for o in modal.location_select.options)


@pytest.mark.asyncio
async def test_off_campus_modal_prefills_existing_address():
    modal = OffCampusPickupModal(_make_person(location="Costa Verde"), _make_user())

    assert modal.address_input.default == "Costa Verde"
    assert modal.address_input.required is True


@pytest.mark.asyncio
async def test_off_campus_modal_has_no_address_default_for_campus_person():
    modal = OffCampusPickupModal(_make_person(location="Sixth"), _make_user())

    assert modal.address_input.default is None


@pytest.mark.asyncio
async def test_sdsu_modal_uses_class_names_mapped_to_ordinals():
    """SDSU riders pick Freshman/Sophomore; pickup info still stores 1st/2nd."""
    modal = SdsuPickupModal(None, _make_user())
    options = [(option.label, option.value) for option in modal.year_select.options]

    assert options == [
        ("Freshman", "1st"),
        ("Sophomore", "2nd"),
        ("Junior", "3rd"),
        ("Senior", "4th"),
    ]


@pytest.mark.asyncio
async def test_ucsd_modals_keep_ordinal_year_labels():
    campus = CampusPickupModal(None, _make_user())
    off_campus = OffCampusPickupModal(None, _make_user())

    for modal in (campus, off_campus):
        labels = [option.label for option in modal.year_select.options]
        assert labels == [year.value for year in ClassYear]


@pytest.mark.asyncio
async def test_sdsu_modal_prefills_matching_class_name():
    modal = SdsuPickupModal(_make_person(year="3rd"), _make_user())

    assert next(o for o in modal.year_select.options if o.default).label == "Junior"


@pytest.mark.asyncio
async def test_sdsu_modal_asks_only_name_and_year():
    modal = SdsuPickupModal(None, _make_user(display_name="Bob"))

    assert modal.name_input.default == "Bob"
    assert not hasattr(modal, "location_select")
    assert not hasattr(modal, "address_input")


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


def _submit_campus(existing=None, name="Alice", year="2nd", location="Sixth"):
    modal = CampusPickupModal(existing, _make_user())
    modal.name_input._value = name
    modal.year_select._values = [year]
    modal.location_select._values = [location]
    return modal


def _submit_off_campus(existing=None, name="Alice", year="2nd", address="  Costa Verde  "):
    modal = OffCampusPickupModal(existing, _make_user())
    modal.name_input._value = name
    modal.year_select._values = [year]
    modal.address_input._value = address
    return modal


def _submit_sdsu(existing=None, name="Alice", year="2nd"):
    modal = SdsuPickupModal(existing, _make_user())
    modal.name_input._value = name
    modal.year_select._values = [year]
    return modal


@pytest.mark.asyncio
async def test_campus_submit_success_created():
    modal = _submit_campus()
    interaction = _make_interaction()
    person = _make_person(location="Sixth")

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))) as mock_register:
        await modal.on_submit(interaction)

    assert mock_register.call_args.kwargs["location"] == "Sixth"
    args, kwargs = interaction.response.send_message.call_args
    assert args[0] == "✅ Thanks **Alice**! We've got you at Sixth."
    assert kwargs.get("ephemeral") is not True


@pytest.mark.asyncio
async def test_campus_rider_is_told_their_usual_pickup_spot():
    modal = _submit_campus(location="ERC")
    interaction = _make_interaction()
    spots = [PickupSpot(name="ERC across from bamboo", maps_url="https://maps.example/erc")]

    with (
        patch(REGISTER, new=AsyncMock(return_value=(_make_person(location="ERC"), True))),
        patch(PICKUP_SPOTS, new=AsyncMock(return_value=spots)),
    ):
        await modal.on_submit(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert args[0] == (
        "✅ Thanks **Alice**! We've got you at ERC. The usual pickup spot is "
        "**ERC across from bamboo** ([Google Maps](https://maps.example/erc)), although "
        f"always make sure to check <#{ChannelIds.REFERENCES__RIDES_ANNOUNCEMENTS}> "
        "for the latest updates."
    )
    # Maps links must not unfurl into previews under the confirmation.
    assert kwargs.get("suppress_embeds") is True


@pytest.mark.asyncio
async def test_marshall_rider_is_shown_both_pickup_spots():
    modal = _submit_campus(location="Marshall")
    interaction = _make_interaction()
    spots = [
        PickupSpot(name="Marshall uppers", maps_url="https://maps.example/marshall"),
        PickupSpot(name="Geisel Loop", maps_url="https://maps.example/geisel"),
    ]

    with (
        patch(REGISTER, new=AsyncMock(return_value=(_make_person(location="Marshall"), True))),
        patch(PICKUP_SPOTS, new=AsyncMock(return_value=spots)),
    ):
        await modal.on_submit(interaction)

    message = interaction.response.send_message.call_args.args[0]
    assert (
        "The usual pickup spot is **Marshall uppers** ([Google Maps](https://maps.example/marshall)) "
        "or **Geisel Loop** ([Google Maps](https://maps.example/geisel)), although"
    ) in message
    assert "sometimes" not in message


@pytest.mark.asyncio
async def test_pickup_lookup_failure_still_confirms():
    """The rider is saved either way, so a lookup error only drops the hint."""
    modal = _submit_campus(location="ERC")
    interaction = _make_interaction()

    with (
        patch(REGISTER, new=AsyncMock(return_value=(_make_person(location="ERC"), True))),
        patch(PICKUP_SPOTS, new=AsyncMock(side_effect=RuntimeError("db down"))),
    ):
        await modal.on_submit(interaction)

    args, _ = interaction.response.send_message.call_args
    assert args[0] == "✅ Thanks **Alice**! We've got you at ERC."


@pytest.mark.asyncio
async def test_coordinator_alert_links_to_pickup_info_without_a_preview():
    modal = _submit_campus(location=_NEEDS_FOLLOWUP_VALUE)
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(location=None), True))):
        await modal.on_submit(interaction)

    send = _coordinators_channel(interaction).send
    assert (
        "Pickup Info page ([link](https://ridebot.springroll.app/pickup-info))"
        in send.call_args.args[0]
    )
    assert send.call_args.kwargs.get("suppress_embeds") is True


@pytest.mark.asyncio
async def test_campus_submit_success_updated():
    modal = _submit_campus()
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(), False))):
        await modal.on_submit(interaction)

    args, _ = interaction.response.send_message.call_args
    assert args[0] == "✅ Updated, **Alice**! We've got you at Sixth."


@pytest.mark.asyncio
async def test_campus_followup_option_stores_no_location():
    modal = _submit_campus(location=_NEEDS_FOLLOWUP_VALUE)
    interaction = _make_interaction()
    person = _make_person(location=None)

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))) as mock_register:
        await modal.on_submit(interaction)

    assert mock_register.call_args.kwargs["location"] is None
    args, _ = interaction.response.send_message.call_args
    assert (
        args[0]
        == "✅ Thanks **Alice**! A ride coordinator will reach out about where to pick you up."
    )


@pytest.mark.asyncio
async def test_followup_notice_leads_with_the_missing_pickup_spot():
    """The no-location case is the one coordinators must act on, so it leads."""
    modal = _submit_campus(location=_NEEDS_FOLLOWUP_VALUE)
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(location=None), True))):
        await modal.on_submit(interaction)

    notice = _coordinators_channel(interaction).send.call_args.args[0]
    assert notice.startswith("🚨 **ACTION NEEDED, no pickup spot**")
    assert "**Alice**" in notice
    assert "ask where they live" in notice
    assert "<#555>" in notice


@pytest.mark.asyncio
async def test_off_campus_submit_uses_trimmed_address():
    modal = _submit_off_campus()
    interaction = _make_interaction()
    person = _make_person(location="Costa Verde")

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))) as mock_register:
        await modal.on_submit(interaction)

    assert mock_register.call_args.kwargs["location"] == "Costa Verde"
    args, _ = interaction.response.send_message.call_args
    assert args[0] == "✅ Thanks **Alice**! We've got you at Costa Verde."


@pytest.mark.asyncio
async def test_sdsu_submit_sends_sdsu_location():
    modal = _submit_sdsu()
    interaction = _make_interaction()
    person = _make_person(location=CampusLivingLocations.SDSU.value)

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))) as mock_register:
        await modal.on_submit(interaction)

    assert mock_register.call_args.kwargs["location"] == CampusLivingLocations.SDSU.value


@pytest.mark.asyncio
async def test_sdsu_rider_is_promised_a_follow_up():
    """SDSU saves a location, but there's no pickup spot behind it yet."""
    modal = _submit_sdsu()
    interaction = _make_interaction()
    person = _make_person(location=CampusLivingLocations.SDSU.value)

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))):
        await modal.on_submit(interaction)

    args, _ = interaction.response.send_message.call_args
    assert args[0] == (
        "✅ Thanks **Alice**! We've got you at SDSU. "
        "A ride coordinator will reach out about where to pick you up."
    )


@pytest.mark.asyncio
async def test_sdsu_notice_is_an_action_needed_alert():
    modal = _submit_sdsu()
    interaction = _make_interaction()
    person = _make_person(location=CampusLivingLocations.SDSU.value)

    with patch(REGISTER, new=AsyncMock(return_value=(person, True))):
        await modal.on_submit(interaction)

    notice = _coordinators_channel(interaction).send.call_args.args[0]
    assert notice.startswith("🚨 **ACTION NEEDED, SDSU rider**")
    assert "no pickup spot" in notice
    assert "<#555>" in notice


# ---------------------------------------------------------------------------
# Coordinator notice and error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_notifies_ride_coordinators():
    modal = _submit_campus()
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(), True))):
        await modal.on_submit(interaction)

    notice = _coordinators_channel(interaction).send.call_args.args[0]
    assert "New hooman" in notice
    assert "**Alice**" in notice
    assert "`@alice`" in notice
    assert "Sixth, 2nd year" in notice
    assert "<#555>" in notice
    # The coordinator copy is deliberately not the rider's confirmation.
    assert notice != "✅ Thanks **Alice**! We've got you at Sixth."


@pytest.mark.asyncio
async def test_off_campus_notice_is_plain_with_no_parenthetical():
    modal = _submit_off_campus()
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(location="Costa Verde"), False))):
        await modal.on_submit(interaction)

    notice = _coordinators_channel(interaction).send.call_args.args[0]
    assert "Updated" in notice
    assert "Costa Verde, 2nd year" in notice
    assert "off campus" not in notice


@pytest.mark.asyncio
async def test_coordinator_notice_failure_is_swallowed():
    modal = _submit_campus()
    interaction = _make_interaction()
    _coordinators_channel(interaction).send = AsyncMock(side_effect=RuntimeError("boom"))

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(), True))):
        await modal.on_submit(interaction)

    # The rider still gets their confirmation even though the notice failed.
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_skips_notice_when_channel_missing():
    modal = _submit_campus()
    interaction = _make_interaction()
    interaction.client.get_channel = MagicMock(return_value=None)

    with patch(REGISTER, new=AsyncMock(return_value=(_make_person(), True))):
        await modal.on_submit(interaction)

    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_validation_error_is_ephemeral():
    modal = _submit_campus()
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(side_effect=PickupInfoValidationError("bad name"))):
        await modal.on_submit(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert "Couldn't save that: bad name" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_conflict_error_is_ephemeral():
    modal = _submit_off_campus()
    interaction = _make_interaction()

    with patch(REGISTER, new=AsyncMock(side_effect=PickupInfoConflictError("taken"))):
        await modal.on_submit(interaction)

    args, kwargs = interaction.response.send_message.call_args
    assert "Couldn't save that: taken" in args[0]
    assert kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_unexpected_error_reports_and_replies_ephemeral():
    modal = _submit_sdsu()
    interaction = _make_interaction()

    with (
        patch(REGISTER, new=AsyncMock(side_effect=RuntimeError("boom"))),
        patch(
            "ridebot.views.pickup_info.send_error_to_discord", new=AsyncMock()
        ) as mock_send_error,
    ):
        await modal.on_submit(interaction)

    mock_send_error.assert_awaited_once()
    _, kwargs = interaction.response.send_message.call_args
    assert kwargs.get("ephemeral") is True
