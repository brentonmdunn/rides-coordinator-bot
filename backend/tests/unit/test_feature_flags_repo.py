"""Unit tests for FeatureFlagsRepository (data access layer)."""

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.enums import FeatureFlagNames
from bot.repositories.feature_flags_repository import FeatureFlagsRepository


@pytest.fixture(autouse=True)
def clear_cache():
    FeatureFlagsRepository._cache.clear()
    yield
    FeatureFlagsRepository._cache.clear()


@pytest.mark.asyncio
async def test_get_feature_flag_status_found():
    """It should return the flag status when found."""
    mock_session = AsyncMock(spec=AsyncSession)

    mock_result = Mock()
    mock_result.one_or_none.return_value = (True,)
    mock_session.execute.return_value = mock_result

    result = await FeatureFlagsRepository.get_feature_flag_status(
        mock_session, FeatureFlagNames.BOT
    )
    assert result is True


@pytest.mark.asyncio
async def test_get_feature_flag_status_not_found():
    """It should return None when the flag doesn't exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = Mock()
    mock_result.one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = await FeatureFlagsRepository.get_feature_flag_status(
        mock_session, FeatureFlagNames.BOT
    )
    assert result is None


@pytest.mark.asyncio
async def test_update_feature_flag_executes_update():
    """It should execute and commit when updating a flag."""
    mock_session = AsyncMock(spec=AsyncSession)

    await FeatureFlagsRepository.update_feature_flag(mock_session, "BOT", True)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_awaited_once()
