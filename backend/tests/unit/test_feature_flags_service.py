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
