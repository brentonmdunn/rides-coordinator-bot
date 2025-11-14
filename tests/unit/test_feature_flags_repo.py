"""Unit tests for FeatureFlagsRepository (data access layer)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.enums import FeatureFlagNames
from app.repositories.feature_flags_repository import FeatureFlagsRepository


@pytest.mark.asyncio
@patch("app.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_get_feature_flag_status_found(mock_session_local):
    """It should return the flag status when found."""
    mock_session = AsyncMock()

    # Mock the object returned by `await session.execute(stmt)`
    mock_result = Mock()
    mock_result.one_or_none.return_value = (True,)
    mock_session.execute.return_value = mock_result

    mock_session_local.return_value.__aenter__.return_value = mock_session

    result = await FeatureFlagsRepository.get_feature_flag_status(FeatureFlagNames.BOT)
    assert result is True


@pytest.mark.asyncio
@patch("app.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_get_feature_flag_status_not_found(mock_session_local):
    """It should return None when the flag doesn't exist."""
    mock_session = AsyncMock()
    mock_result = Mock()
    mock_result.one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    mock_session_local.return_value.__aenter__.return_value = mock_session

    result = await FeatureFlagsRepository.get_feature_flag_status(FeatureFlagNames.BOT)
    assert result is None


@pytest.mark.asyncio
@patch("app.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_update_feature_flag_executes_update(mock_session_local):
    """It should execute and commit when updating a flag."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    await FeatureFlagsRepository.update_feature_flag("BOT", True)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_awaited_once()
