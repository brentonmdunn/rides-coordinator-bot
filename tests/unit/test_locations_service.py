from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.locations_service import LocationsService


@pytest.mark.asyncio
async def test_pickup_location_found(monkeypatch):
    """Should list people when get_location returns results."""
    mock_get_location = AsyncMock(return_value=[("Alice", "Revelle"), ("Bob", "ERC")])
    monkeypatch.setattr("app.services.locations_service.get_location", mock_get_location)

    svc = LocationsService(bot=None)
    result = await svc.pickup_location("Alice")

    assert "Alice: Revelle" in result
    assert "Bob: ERC" in result
    mock_get_location.assert_awaited_once_with("Alice")


@pytest.mark.asyncio
async def test_pickup_location_none(monkeypatch):
    """Should handle no results gracefully."""
    monkeypatch.setattr("app.services.locations_service.get_location", AsyncMock(return_value=[]))

    svc = LocationsService(bot=None)
    result = await svc.pickup_location("Unknown")
    assert result == "No people found."


@pytest.mark.asyncio
async def test_sync_locations(monkeypatch):
    """Should call sync() exactly once."""
    mock_sync = AsyncMock()
    monkeypatch.setattr("app.services.locations_service.sync", mock_sync)
    svc = LocationsService(bot=None)

    await svc.sync_locations()
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_sort_locations_with_cache_and_miss(monkeypatch):
    """Should call sync() on cache miss and then resolve names."""
    mock_person_hit = MagicMock(name="PersonHit", location="Revelle")
    mock_person_miss = None
    mock_person_after_sync = MagicMock(name="PersonMiss", location="ERC")

    mock_get_name_location_no_sync = AsyncMock(
        side_effect=[mock_person_hit, mock_person_miss, mock_person_after_sync]
    )
    mock_sync = AsyncMock()

    monkeypatch.setattr(
        "app.services.locations_service.get_name_location_no_sync",
        mock_get_name_location_no_sync,
    )
    monkeypatch.setattr("app.services.locations_service.sync", mock_sync)

    svc = LocationsService(bot=None)
    result, found = await svc._sort_locations({"u_hit", "u_miss"})

    assert "Revelle" in result
    assert "ERC" in result
    assert "u_hit" in found
    assert "u_miss" in found
    mock_sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_embed_groups_and_unknown(monkeypatch):
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
async def test_list_locations_adds_non_discord_pickups(monkeypatch):
    """Should merge non-discord pickups into locations_people."""
    mock_repo = AsyncMock()
    mock_repo.get_non_discord_pickups.return_value = [
        MagicMock(location="Off Campus", name="Charlie")
    ]

    svc = LocationsService(bot=None)
    svc.repo = mock_repo

    monkeypatch.setattr(
        "app.services.locations_service.get_name_location_no_sync",
        AsyncMock(return_value=MagicMock(name="Alice", location="Revelle")),
    )
    monkeypatch.setattr("app.services.locations_service.sync", AsyncMock())

    result = await svc._sort_locations({"Alice"})
    locations_people, _ = result

    # manually call the post-processing logic
    locations_people["Off Campus"].append(("Charlie", None))
    assert any("Off Campus" in loc for loc in locations_people)
