"""Unit tests for FeatureFlagsService (business logic layer)."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.core.enums import FeatureFlagNames
from bot.services.feature_flags_service import FeatureFlagsService


@pytest.mark.asyncio
async def test_validate_feature_name_valid():
    """Should return enum member for valid name."""
    service = FeatureFlagsService()
    result = await service.validate_feature_name("bot")
    assert result == FeatureFlagNames.BOT


@pytest.mark.asyncio
async def test_validate_feature_name_invalid():
    """Should return None for invalid flag."""
    service = FeatureFlagsService()
    result = await service.validate_feature_name("INVALID_FLAG")
    assert result is None


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_feature_flag",
    new_callable=AsyncMock,
)
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.update_feature_flag",
    new_callable=AsyncMock,
)
@patch("bot.services.feature_flags_service.AsyncSessionLocal")
async def test_modify_feature_flag_updates(mock_session_local, _, mock_get):
    """Should update feature flag and return success message."""
    mock_get.return_value = type("Flag", (), {"enabled": False})

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session

    service = FeatureFlagsService()
    success, msg = await service.modify_feature_flag("BOT", True)
    assert success is True
    assert "✅" in msg


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_feature_flag",
    new_callable=AsyncMock,
)
@patch("bot.services.feature_flags_service.AsyncSessionLocal")
async def test_modify_feature_flag_not_found(mock_session_local, mock_get):
    """Should handle not found flags gracefully."""
    mock_get.return_value = None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session

    service = FeatureFlagsService()
    success, msg = await service.modify_feature_flag("NONEXISTENT", True)
    assert success is False
    assert "not found" in msg


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_feature_flag",
    new_callable=AsyncMock,
)
@patch("bot.services.feature_flags_service.AsyncSessionLocal")
async def test_modify_feature_flag_already_enabled(mock_session_local, mock_get):
    """Should not update if already in desired state."""
    mock_get.return_value = type("Flag", (), {"enabled": True})

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session

    service = FeatureFlagsService()
    success, msg = await service.modify_feature_flag("BOT", True)
    assert success is False
    assert "already" in msg


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_feature_flag",
    new_callable=AsyncMock,
)
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.update_feature_flag",
    new_callable=AsyncMock,
)
async def test_modify_feature_flag_with_provided_session(mock_update, mock_get):
    """modify_feature_flag should use the provided session rather than creating a new one."""
    mock_get.return_value = type("Flag", (), {"enabled": False})

    mock_session = AsyncMock()
    service = FeatureFlagsService()
    success, msg = await service.modify_feature_flag("BOT", True, session=mock_session)

    assert success is True
    assert "✅" in msg
    mock_update.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_all_feature_flags",
    new_callable=AsyncMock,
)
@patch("bot.services.feature_flags_service.AsyncSessionLocal")
async def test_list_feature_flags_embed_no_session(mock_session_local, mock_get_all):
    """list_feature_flags_embed should create a session internally when none is provided."""
    import discord

    flag_enabled = type("Flag", (), {"feature": "bot", "enabled": True})
    flag_disabled = type("Flag", (), {"feature": "rides", "enabled": False})
    mock_get_all.return_value = [flag_enabled, flag_disabled]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session_local.return_value = mock_session

    service = FeatureFlagsService()
    embed = await service.list_feature_flags_embed()

    assert isinstance(embed, discord.Embed)
    assert embed.title == "⚙️ Feature Flag Status"
    assert len(embed.fields) == 2


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_all_feature_flags",
    new_callable=AsyncMock,
)
async def test_list_feature_flags_embed_with_session(mock_get_all):
    """list_feature_flags_embed should use the provided session directly."""
    import discord

    flag = type("Flag", (), {"feature": "bot", "enabled": True})
    mock_get_all.return_value = [flag]

    mock_session = AsyncMock()
    service = FeatureFlagsService()
    embed = await service.list_feature_flags_embed(session=mock_session)

    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) == 1
    field = embed.fields[0]
    assert "bot" in field.name
    assert "Enabled" in field.value


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_all_feature_flags",
    new_callable=AsyncMock,
)
async def test_list_feature_flags_embed_disabled_flag(mock_get_all):
    """Disabled flags should show the disabled status icon and text."""
    import discord

    flag = type("Flag", (), {"feature": "rides", "enabled": False})
    mock_get_all.return_value = [flag]

    mock_session = AsyncMock()
    service = FeatureFlagsService()
    embed = await service.list_feature_flags_embed(session=mock_session)

    assert isinstance(embed, discord.Embed)
    field = embed.fields[0]
    assert "rides" in field.name
    assert "Disabled" in field.value


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_all_feature_flags",
    new_callable=AsyncMock,
)
async def test_list_feature_flags_embed_empty(mock_get_all):
    """list_feature_flags_embed with no flags returns an embed with no fields."""
    import discord

    mock_get_all.return_value = []
    mock_session = AsyncMock()

    service = FeatureFlagsService()
    embed = await service.list_feature_flags_embed(session=mock_session)

    assert isinstance(embed, discord.Embed)
    assert len(embed.fields) == 0


@pytest.mark.asyncio
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.get_feature_flag",
    new_callable=AsyncMock,
)
@patch(
    "bot.services.feature_flags_service.FeatureFlagsRepository.update_feature_flag",
    new_callable=AsyncMock,
)
async def test_modify_feature_flag_disable_existing(mock_update, mock_get):
    """Should successfully disable a currently enabled flag."""
    mock_get.return_value = type("Flag", (), {"enabled": True})

    mock_session = AsyncMock()
    service = FeatureFlagsService()
    success, msg = await service.modify_feature_flag("BOT", False, session=mock_session)

    assert success is True
    assert "disabled" in msg
    mock_update.assert_awaited_once()
