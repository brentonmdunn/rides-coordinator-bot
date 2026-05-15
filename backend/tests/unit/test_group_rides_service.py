"""Unit tests for GroupRidesService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.core.enums import (
    CampusLivingLocations,
    JobName,
    PickupLocations,
)
from bot.core.schemas import Identity, Passenger
from bot.services.group_rides_service import (
    EVENT_END_LEAVE_TIMES,
    GroupRidesService,
    living_to_pickup,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> GroupRidesService:
    """Return a GroupRidesService with a dummy bot and mocked sub-services."""
    svc = GroupRidesService.__new__(GroupRidesService)
    svc.bot = MagicMock()
    svc.llm_service = MagicMock()
    svc.locations_service = MagicMock()
    svc.repo = MagicMock()
    svc._route_service = MagicMock()
    return svc


def _make_passenger(
    name: str, username: str, living: CampusLivingLocations, pickup: PickupLocations
) -> Passenger:
    return Passenger(
        identity=Identity(name=name, username=username),
        living_location=living,
        pickup_location=pickup,
    )


# ---------------------------------------------------------------------------
# _get_living_location
# ---------------------------------------------------------------------------


def test_get_living_location_erc_case_insensitive():
    assert GroupRidesService._get_living_location("erc") == CampusLivingLocations.ERC
    assert GroupRidesService._get_living_location("ERC") == CampusLivingLocations.ERC


def test_get_living_location_title_case():
    assert GroupRidesService._get_living_location("seventh") == CampusLivingLocations.SEVENTH
    assert GroupRidesService._get_living_location("Marshall") == CampusLivingLocations.MARSHALL


def test_get_living_location_invalid_raises():
    with pytest.raises(ValueError):
        GroupRidesService._get_living_location("atlantis")


# ---------------------------------------------------------------------------
# _get_pickup_location
# ---------------------------------------------------------------------------


def test_get_pickup_location_maps_living_to_pickup():
    for living, expected_pickup in living_to_pickup.items():
        result = GroupRidesService._get_pickup_location(living)
        assert result == expected_pickup


def test_get_pickup_location_revelle_maps_to_eighth():
    result = GroupRidesService._get_pickup_location(CampusLivingLocations.REVELLE)
    assert result == PickupLocations.EIGHTH


# ---------------------------------------------------------------------------
# _determine_event_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_determine_event_type_friday():
    svc = _make_service()
    job, leave_time = await svc._determine_event_type("please sign up for friday fellowship rides")
    assert job == JobName.FRIDAY
    assert leave_time == EVENT_END_LEAVE_TIMES[JobName.FRIDAY]


@pytest.mark.asyncio
async def test_determine_event_type_sunday():
    svc = _make_service()
    job, leave_time = await svc._determine_event_type("sunday service sign up")
    assert job == JobName.SUNDAY
    assert leave_time == EVENT_END_LEAVE_TIMES[JobName.SUNDAY]


@pytest.mark.asyncio
async def test_determine_event_type_invalid_raises():
    svc = _make_service()
    with pytest.raises(ValueError, match=r"friday.*sunday"):
        await svc._determine_event_type("wednesday potluck")


# ---------------------------------------------------------------------------
# _split_on_off_campus
# ---------------------------------------------------------------------------


def test_split_on_off_campus_known_location():
    svc = _make_service()
    locations_people = {
        "Seventh": [("Alice", "alice")],
        "ERC": [("Bob", "bob")],
    }
    passengers_by_location, off_campus = svc._split_on_off_campus(locations_people)

    assert off_campus == {}
    # Both campus locations should appear in passengers_by_location
    assert any(
        p.identity.name == "Alice"
        for passengers in passengers_by_location.values()
        for p in passengers
    )
    assert any(
        p.identity.name == "Bob"
        for passengers in passengers_by_location.values()
        for p in passengers
    )


def test_split_on_off_campus_off_campus_location():
    svc = _make_service()
    locations_people = {
        "Some off-campus address": [("Charlie", "charlie")],
    }
    passengers_by_location, off_campus = svc._split_on_off_campus(locations_people)

    assert passengers_by_location == {}
    assert "Some off-campus address" in off_campus


def test_split_on_off_campus_mixed():
    svc = _make_service()
    locations_people = {
        "Muir": [("Alice", "alice")],
        "123 Ocean St": [("Bob", "bob")],
    }
    passengers_by_location, off_campus = svc._split_on_off_campus(locations_people)

    assert "123 Ocean St" in off_campus
    assert any(
        p.identity.name == "Alice"
        for passengers in passengers_by_location.values()
        for p in passengers
    )


def test_split_on_off_campus_erc_handled():
    """ERC living location should be mapped via _get_living_location (lowercased 'erc')."""
    svc = _make_service()
    locations_people = {"ERC": [("Alice", "alice")]}
    passengers_by_location, off_campus = svc._split_on_off_campus(locations_people)
    assert off_campus == {}
    assert len(passengers_by_location) > 0


# ---------------------------------------------------------------------------
# _validate_capacity
# ---------------------------------------------------------------------------


def test_validate_capacity_sufficient():
    svc = _make_service()
    passengers_by_location = {
        PickupLocations.SEVENTH: [
            _make_passenger("A", "a", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
            _make_passenger("B", "b", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
        ]
    }
    result = svc._validate_capacity("44", passengers_by_location)
    assert result == [4, 4]


def test_validate_capacity_exact_fit():
    svc = _make_service()
    passengers_by_location = {
        PickupLocations.SEVENTH: [
            _make_passenger("A", "a", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
        ]
    }
    result = svc._validate_capacity("1", passengers_by_location)
    assert result == [1]


def test_validate_capacity_insufficient_raises():
    svc = _make_service()
    passengers_by_location = {
        PickupLocations.SEVENTH: [
            _make_passenger("A", "a", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
            _make_passenger("B", "b", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
            _make_passenger("C", "c", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
            _make_passenger("D", "d", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
            _make_passenger("E", "e", CampusLivingLocations.ERC, PickupLocations.SEVENTH),
        ]
    }
    with pytest.raises(ValueError, match="Insufficient driver capacity"):
        svc._validate_capacity("1", passengers_by_location)


def test_validate_capacity_non_integer_raises():
    svc = _make_service()
    with pytest.raises(ValueError, match="integers"):
        svc._validate_capacity("4x4", {})


def test_validate_capacity_spaced_digits():
    svc = _make_service()
    passengers_by_location: dict = {}
    result = svc._validate_capacity("4 4 4", passengers_by_location)
    assert result == [4, 4, 4]


# ---------------------------------------------------------------------------
# _filter_class_attendees
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_class_attendees_no_class_message():
    """If no class message found, original set is returned unchanged."""
    svc = _make_service()
    svc.locations_service._find_correct_message = AsyncMock(return_value=None)

    original = {"alice", "bob"}
    result = await svc._filter_class_attendees(original, channel_id=12345)
    assert result == original


@pytest.mark.asyncio
async def test_filter_class_attendees_removes_class_goers():
    svc = _make_service()
    svc.locations_service._find_correct_message = AsyncMock(return_value=9999)
    # list_locations returns (locations_people, usernames_reacted, location_found)
    svc.locations_service.list_locations = AsyncMock(return_value=({}, {"alice"}, {"alice"}))

    result = await svc._filter_class_attendees({"alice", "bob"}, channel_id=12345)
    assert result == {"bob"}


# ---------------------------------------------------------------------------
# get_pickup_location_fuzzy / make_route delegation
# ---------------------------------------------------------------------------


def test_get_pickup_location_fuzzy_delegates():
    svc = _make_service()
    with patch(
        "bot.services.group_rides_service.RouteService.get_pickup_location_fuzzy",
        return_value=PickupLocations.SEVENTH,
    ) as mock_fuzzy:
        result = svc.get_pickup_location_fuzzy("seventh mail")
        mock_fuzzy.assert_called_once_with("seventh mail")
        assert result == PickupLocations.SEVENTH


def test_make_route_delegates():
    svc = _make_service()
    with patch(
        "bot.services.group_rides_service.RouteService.make_route",
        return_value="some route string",
    ) as mock_route:
        result = svc.make_route("SEVENTH ERC", "7:00pm")
        mock_route.assert_called_once_with("SEVENTH ERC", "7:00pm")
        assert result == "some route string"


# ---------------------------------------------------------------------------
# group_rides_api
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_rides_api_raises_when_no_message_id_or_day():
    svc = _make_service()
    with pytest.raises(ValueError, match="message_id or day"):
        await svc.group_rides_api(message_id=None, day=None)


@pytest.mark.asyncio
async def test_group_rides_api_raises_when_invalid_day():
    svc = _make_service()
    with pytest.raises(ValueError):
        # JobName("wednesday") raises ValueError since it's not a valid JobName
        await svc.group_rides_api(day="wednesday")


@pytest.mark.asyncio
async def test_group_rides_api_day_message_not_found_raises():
    svc = _make_service()
    svc.locations_service._find_correct_message = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Could not find"):
        await svc.group_rides_api(day="friday")


@pytest.mark.asyncio
async def test_group_rides_api_success():
    svc = _make_service()
    svc._process_ride_grouping = AsyncMock(
        return_value=["summary block", "grouping1", "```code```", "grouping2"]
    )

    result = await svc.group_rides_api(message_id=1234, driver_capacity="44444")

    assert result["summary"] == "summary block"
    assert "grouping1" in result["groupings"]
    assert "grouping2" in result["groupings"]
    # code blocks starting with ``` should be filtered out
    assert "```code```" not in result["groupings"]


@pytest.mark.asyncio
async def test_group_rides_api_uses_default_channel_id():
    svc = _make_service()
    svc._process_ride_grouping = AsyncMock(return_value=["summary"])

    await svc.group_rides_api(message_id=9999)

    # Verify _process_ride_grouping was called (channel_id should default to rides announcements)
    svc._process_ride_grouping.assert_awaited_once()
    call_args = svc._process_ride_grouping.call_args
    assert call_args.args[2] is not None  # channel_id positional arg


# ---------------------------------------------------------------------------
# _process_ride_grouping — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_ride_grouping_raises_when_message_fetch_fails():
    svc = _make_service()
    svc.locations_service.list_locations = AsyncMock(
        return_value=({"Seventh": [("Alice", "alice")]}, {"alice"}, {"alice"})
    )
    svc.repo.fetch_message = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Could not fetch"):
        await svc._process_ride_grouping(1234, "44444", 9999)


@pytest.mark.asyncio
async def test_process_ride_grouping_raises_on_unknown_location():
    svc = _make_service()
    # user reacted but location wasn't found
    svc.locations_service.list_locations = AsyncMock(return_value=({}, {"alice"}, set()))
    fake_msg = MagicMock()
    fake_msg.content = "friday fellowship"
    fake_msg.embeds = []
    svc.repo.fetch_message = AsyncMock(return_value=fake_msg)

    with pytest.raises(ValueError, match="Unknown location"):
        await svc._process_ride_grouping(1234, "44444", 9999)


@pytest.mark.asyncio
async def test_process_ride_grouping_raises_on_llm_error_key():
    svc = _make_service()
    svc.locations_service.list_locations = AsyncMock(
        return_value=({"Seventh": [("Alice", "alice")]}, {"alice"}, {"alice"})
    )
    fake_msg = MagicMock()
    fake_msg.content = "friday fellowship"
    fake_msg.embeds = []
    svc.repo.fetch_message = AsyncMock(return_value=fake_msg)
    svc.llm_service.generate_ride_groups = MagicMock(return_value={"error": "bad input"})

    with (
        patch(
            "bot.services.group_rides_service.asyncio.to_thread",
            new=AsyncMock(return_value={"error": "bad input"}),
        ),
        pytest.raises(ValueError, match="LLM returned with error"),
    ):
        await svc._process_ride_grouping(1234, "44444", 9999)


@pytest.mark.asyncio
async def test_process_ride_grouping_raises_on_llm_exception():
    svc = _make_service()
    svc.locations_service.list_locations = AsyncMock(
        return_value=({"Seventh": [("Alice", "alice")]}, {"alice"}, {"alice"})
    )
    fake_msg = MagicMock()
    fake_msg.content = "friday fellowship"
    fake_msg.embeds = []
    svc.repo.fetch_message = AsyncMock(return_value=fake_msg)

    with (
        patch(
            "bot.services.group_rides_service.asyncio.to_thread",
            new=AsyncMock(side_effect=RuntimeError("LLM down")),
        ),
        patch("bot.services.group_rides_service.send_error_to_discord", new=AsyncMock()),
        pytest.raises(ValueError, match="Could not process"),
    ):
        await svc._process_ride_grouping(1234, "44444", 9999)


# ---------------------------------------------------------------------------
# group_rides (Discord interaction path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_group_rides_sends_error_on_value_error():
    svc = _make_service()
    interaction = AsyncMock()
    svc._process_ride_grouping = AsyncMock(side_effect=ValueError("bad capacity"))

    await svc.group_rides(interaction, driver_capacity="x", message_id=1234)

    interaction.response.defer.assert_awaited_once()
    interaction.followup.send.assert_awaited_once()
    args = interaction.followup.send.call_args[0]
    assert "bad capacity" in args[0]


@pytest.mark.asyncio
async def test_group_rides_sends_multiple_messages():
    svc = _make_service()
    interaction = AsyncMock()
    svc._process_ride_grouping = AsyncMock(return_value=["first", "second", "third"])

    await svc.group_rides(interaction, driver_capacity="444", message_id=1234)

    interaction.followup.send.assert_awaited_once_with("first")
    assert interaction.channel.send.await_count == 2


@pytest.mark.asyncio
async def test_group_rides_day_not_found_sends_message():
    svc = _make_service()
    interaction = AsyncMock()
    svc.locations_service._find_correct_message = AsyncMock(return_value=None)

    await svc.group_rides(interaction, driver_capacity="444", day="friday")

    interaction.followup.send.assert_awaited_once()
    args = interaction.followup.send.call_args[0]
    assert "Could not find" in args[0]
