from collections import defaultdict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ridebot.services.locations_service import LocationsService
from ridebot.utils.custom_exceptions import NoMatchingMessageFoundError
from shared.core.enums import JobName, RideOption


@pytest.mark.asyncio
async def test_pickup_location_found():
    """Should list people when get_location returns results."""
    svc = LocationsService(bot=None)
    svc.get_location: Any = AsyncMock(return_value=[("Alice", "Revelle"), ("Bob", "ERC")])

    result = await svc.pickup_location("Alice")

    assert "Alice: Revelle" in result
    assert "Bob: ERC" in result
    svc.get_location.assert_awaited_once_with("Alice")


@pytest.mark.asyncio
async def test_pickup_location_none():
    """Should handle no results gracefully."""
    svc = LocationsService(bot=None)
    svc.get_location: Any = AsyncMock(return_value=[])

    result = await svc.pickup_location("Unknown")
    assert result == "No people found."


@pytest.mark.asyncio
async def test_sort_locations_skips_unmatched():
    """Should skip usernames with no matching location, no resync."""
    # _sort_locations uses person[0] (name) and person[1] (location), so use tuples
    people = {"u_hit": ("PersonHit", "Revelle"), "u_miss": None}

    svc = LocationsService(bot=None)
    # Keyed by username: set iteration order is not stable across runs.
    svc.get_name_location_no_sync: Any = AsyncMock(side_effect=people.get)

    result, found = await svc._sort_locations({"u_hit", "u_miss"})

    assert "Revelle" in result
    assert "u_hit" in found
    assert "u_miss" not in found


@pytest.mark.asyncio
async def test_build_embed_groups_and_unknown():
    """Should build embed grouping correctly with unknown users."""
    import discord

    svc = LocationsService(bot=None)
    locations_people = {
        "revelle": [("Alice", "alice#123")],
        "warren": [("Bob", "bob#456")],
        "random place": [("Eve", "eve#789")],
    }
    usernames_reacted = {"alice#123", "bob#456", "unknown_user"}
    location_found = {"alice#123", "bob#456"}

    embed = svc._housing.build_embed(
        locations_people, usernames_reacted, location_found, option=RideOption.FRIDAY
    )
    assert isinstance(embed, discord.Embed)
    assert any(f.name.startswith("🏫") for f in embed.fields)  # Scholars group
    assert any("Unknown Location" in f.name for f in embed.fields)
    assert "unknown_user" in embed.fields[-1].value


@pytest.mark.asyncio
async def test_list_locations_invalid_day():
    """Should raise ValueError for invalid day input."""
    svc = LocationsService(bot=None)
    with pytest.raises(ValueError):
        await svc.list_locations(day="Monday")


@pytest.mark.asyncio
async def test_list_locations_adds_non_discord_pickups():
    """Should merge non-discord pickups into locations_people."""
    mock_repo = AsyncMock()
    mock_repo.get_non_discord_pickups.return_value = [
        MagicMock(location="Off Campus", name="Charlie")
    ]

    svc = LocationsService(bot=None)
    svc.repo: Any = mock_repo  # type: ignore[attr-defined]
    svc.get_name_location_no_sync: Any = AsyncMock(
        return_value=("Alice", "Revelle")  # _sort_locations uses person[0]/person[1]
    )

    result = await svc._sort_locations({"Alice"})
    locations_people, _ = result

    # manually call the post-processing logic (simulating what list_locations does)
    pickups = await mock_repo.get_non_discord_pickups(JobName.FRIDAY)
    for pickup in pickups:
        locations_people[pickup.location].append((pickup.name, None))

    assert any("Off Campus" in loc for loc in locations_people)


@pytest.mark.asyncio
async def test_get_location_returns_results():
    """When DB returns results, they're returned directly."""
    svc = LocationsService(bot=None)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("ridebot.services.locations_service.AsyncSessionLocal", return_value=mock_session_cm),
        patch(
            "ridebot.services.locations_service.LocationsRepository.get_location_check_name_and_discord",
            new_callable=AsyncMock,
            return_value=[("Alice", "Revelle")],
        ),
    ):
        result = await svc.get_location("Alice")

    assert result == [("Alice", "Revelle")]


@pytest.mark.asyncio
async def test_get_location_returns_none_on_miss():
    """If nothing matches, None is returned with no resync."""
    svc = LocationsService(bot=None)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("ridebot.services.locations_service.AsyncSessionLocal", return_value=mock_session_cm),
        patch(
            "ridebot.services.locations_service.LocationsRepository.get_location_check_name_and_discord",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await svc.get_location("Nobody")

    assert result is None


@pytest.mark.asyncio
async def test_get_location_discord_only_uses_discord_check():
    svc = LocationsService(bot=None)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("ridebot.services.locations_service.AsyncSessionLocal", return_value=mock_session_cm),
        patch(
            "ridebot.services.locations_service.LocationsRepository.get_location_check_discord",
            new_callable=AsyncMock,
            return_value=[("Alice", "Revelle")],
        ) as mock_discord_check,
    ):
        result = await svc.get_location("alice", discord_only=True)

    assert result == [("Alice", "Revelle")]
    mock_discord_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_name_location_no_sync_delegates_to_repo():
    svc = LocationsService(bot=None)
    fake_person = MagicMock(name="Alice", location="Revelle")

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("ridebot.services.locations_service.AsyncSessionLocal", return_value=mock_session_cm),
        patch(
            "ridebot.services.locations_service.LocationsRepository.get_name_location",
            new_callable=AsyncMock,
            return_value=fake_person,
        ),
    ):
        result = await svc.get_name_location_no_sync("alice")

    assert result is fake_person


@pytest.mark.asyncio
async def test_list_locations_wrapper_sends_embed():
    svc = LocationsService(bot=None)
    interaction = AsyncMock()

    locations_people = defaultdict(list)
    locations_people["Revelle"].append(("Alice", "alice"))
    svc.list_locations = AsyncMock(return_value=(locations_people, {"alice"}, {"alice"}))

    import discord

    fake_embed = MagicMock(spec=discord.Embed)
    svc._housing.build_embed = MagicMock(return_value=fake_embed)

    await svc.list_locations_wrapper(interaction, day=JobName.FRIDAY)

    interaction.response.send_message.assert_awaited_once_with(embed=fake_embed)


@pytest.mark.asyncio
async def test_list_locations_wrapper_handles_no_matching_message():
    svc = LocationsService(bot=None)
    interaction = AsyncMock()
    svc.list_locations = AsyncMock(side_effect=NoMatchingMessageFoundError())

    await svc.list_locations_wrapper(interaction)

    args = interaction.response.send_message.call_args[0]
    assert "No matching message" in args[0]


@pytest.mark.asyncio
async def test_list_locations_wrapper_handles_unexpected_error():
    svc = LocationsService(bot=None)
    interaction = AsyncMock()
    svc.list_locations = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("ridebot.services.locations_service.send_error_to_discord", new_callable=AsyncMock):
        await svc.list_locations_wrapper(interaction)

    call_kwargs = interaction.response.send_message.call_args[1]
    assert call_kwargs.get("ephemeral") is True


@pytest.mark.asyncio
async def test_list_locations_no_day_uses_message_id():
    """list_locations with only message_id (no day) fetches channel and message."""
    svc = LocationsService(bot=None)

    fake_message = MagicMock()
    fake_message.content = "some ride message"
    fake_message.embeds = []

    fake_channel = AsyncMock()
    fake_channel.fetch_message = AsyncMock(return_value=fake_message)
    svc.bot = MagicMock()
    svc.bot.get_channel.return_value = fake_channel

    svc.get_usernames_who_reacted = AsyncMock(return_value={"alice"})
    svc._find_correct_message = AsyncMock(return_value=None)  # not called in message_id path

    fake_person = MagicMock()
    fake_person.location = "Revelle"
    fake_person.name = "Alice"
    svc.get_name_location_no_sync = AsyncMock(return_value=fake_person)

    mock_session = AsyncMock()
    mock_session_cm = MagicMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("ridebot.services.locations_service.AsyncSessionLocal", return_value=mock_session_cm),
        patch(
            "ridebot.services.locations_service.LocationsRepository.get_non_discord_pickups",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        _, reacted, _ = await svc.list_locations(message_id=999)

    assert "alice" in reacted
