"""Unit tests for FeatureFlagsRepository caching behavior."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from bot.core.enums import FeatureFlagNames
from bot.repositories.feature_flags_repository import FeatureFlagsRepository


@pytest.fixture(autouse=True)
def clear_cache():
    FeatureFlagsRepository._cache.clear()
    yield
    FeatureFlagsRepository._cache.clear()


@pytest.mark.asyncio
@patch("bot.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_initialize_cache(mock_session_local):
    """It should populate the cache from the database."""
    mock_session = AsyncMock()
    mock_result = Mock()

    # Mock DB returning two flags
    flag1 = Mock(feature="TEST_FLAG_1", enabled=True)
    flag2 = Mock(feature="TEST_FLAG_2", enabled=False)
    mock_result.scalars.return_value.all.return_value = [flag1, flag2]

    mock_session.execute.return_value = mock_result
    mock_session_local.return_value.__aenter__.return_value = mock_session

    await FeatureFlagsRepository.initialize_cache()

    assert FeatureFlagsRepository._cache["TEST_FLAG_1"] is True
    assert FeatureFlagsRepository._cache["TEST_FLAG_2"] is False
    assert len(FeatureFlagsRepository._cache) == 2


@pytest.mark.asyncio
@patch("bot.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_get_feature_flag_status_uses_cache(mock_session_local):
    """It should use the cache and not hit the DB if the flag is cached."""
    # Pre-populate cache
    FeatureFlagsRepository._cache[FeatureFlagNames.BOT.value] = True

    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    result = await FeatureFlagsRepository.get_feature_flag_status(FeatureFlagNames.BOT)

    assert result is True
    # Verify DB was NOT called
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
@patch("bot.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_get_feature_flag_status_updates_cache_on_miss(mock_session_local):
    """It should query DB on cache miss and update the cache."""
    mock_session = AsyncMock()
    mock_result = Mock()
    mock_result.one_or_none.return_value = (True,)
    mock_session.execute.return_value = mock_result
    mock_session_local.return_value.__aenter__.return_value = mock_session

    # Ensure cache is empty for this flag
    assert FeatureFlagNames.BOT.value not in FeatureFlagsRepository._cache

    result = await FeatureFlagsRepository.get_feature_flag_status(FeatureFlagNames.BOT)

    assert result is True
    # Verify DB WAS called
    mock_session.execute.assert_called_once()
    # Verify cache was updated
    assert FeatureFlagsRepository._cache[FeatureFlagNames.BOT.value] is True


@pytest.mark.asyncio
@patch("bot.repositories.feature_flags_repository.AsyncSessionLocal")
async def test_update_feature_flag_updates_cache(mock_session_local):
    """It should update the cache when a flag is modified."""
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    # Pre-populate cache with old value
    FeatureFlagsRepository._cache["TEST_FLAG"] = False

    await FeatureFlagsRepository.update_feature_flag("TEST_FLAG", True)

    # Verify DB update was called
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_awaited_once()

    # Verify cache was updated
    assert FeatureFlagsRepository._cache["TEST_FLAG"] is True
