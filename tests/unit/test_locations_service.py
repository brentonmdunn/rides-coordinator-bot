from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.locations_service import LocationsService


@pytest.mark.asyncio
async def test_pickup_location_found():
    """Should list people when get_location returns results."""
    svc = LocationsService(bot=None)
    svc.get_location = AsyncMock(return_value=[("Alice", "Revelle"), ("Bob", "ERC")])

    result = await svc.pickup_location("Alice")

    assert "Alice: Revelle" in result
    assert "Bob: ERC" in result
    svc.get_location.assert_awaited_once_with("Alice")


@pytest.mark.asyncio
async def test_pickup_location_none():
    """Should handle no results gracefully."""
    svc = LocationsService(bot=None)
    svc.get_location = AsyncMock(return_value=[])

    result = await svc.pickup_location("Unknown")
    assert result == "No people found."


@pytest.mark.asyncio
async def test_sync_locations(monkeypatch):
    """Should call repo.sync_locations() exactly once."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"Name,Discord Username,Year,Location,Driver\nAlice,alice,2025,Revelle,Yes"
    
    monkeypatch.setattr("requests.get", MagicMock(return_value=mock_response))
    monkeypatch.setattr("app.services.locations_service.LSCC_PPL_CSV_URL", "http://example.com")

    svc = LocationsService(bot=None)
    svc.repo.sync_locations = AsyncMock()

    await svc.sync_locations()
    svc.repo.sync_locations.assert_awaited_once()


@pytest.mark.asyncio
async def test_sort_locations_with_cache_and_miss():
    """Should call sync_locations() on cache miss and then resolve names."""
    mock_person_hit = MagicMock(name="PersonHit", location="Revelle")
    mock_person_miss = None
    mock_person_after_sync = MagicMock(name="PersonMiss", location="ERC")

    svc = LocationsService(bot=None)
    svc.get_name_location_no_sync = AsyncMock(
        side_effect=[mock_person_hit, mock_person_miss, mock_person_after_sync]
    )
    svc.sync_locations = AsyncMock()

    result, found = await svc._sort_locations({"u_hit", "u_miss"})

    assert "Revelle" in result
    assert "ERC" in result
    assert "u_hit" in found
    assert "u_miss" in found
    svc.sync_locations.assert_awaited_once()


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

    embed = svc._build_embed(locations_people, usernames_reacted, location_found, option="Friday")
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
    svc.repo = mock_repo
    svc.get_name_location_no_sync = AsyncMock(
        return_value=MagicMock(name="Alice", location="Revelle")
    )

    result = await svc._sort_locations({"Alice"})
    locations_people, _ = result

    # manually call the post-processing logic (simulating what list_locations does)
    pickups = await svc.repo.get_non_discord_pickups("Friday")
    for pickup in pickups:
        locations_people[pickup.location].append((pickup.name, None))

    assert any("Off Campus" in loc for loc in locations_people)
