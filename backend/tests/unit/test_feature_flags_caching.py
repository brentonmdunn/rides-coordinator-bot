"""Unit tests for FeatureFlagsRepository caching behavior."""

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
async def test_initialize_cache():
    """It should populate the cache from the database."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = Mock()

    flag1 = Mock(feature="TEST_FLAG_1", enabled=True)
    flag2 = Mock(feature="TEST_FLAG_2", enabled=False)
    mock_result.scalars.return_value.all.return_value = [flag1, flag2]

    mock_session.execute.return_value = mock_result

    await FeatureFlagsRepository.initialize_cache(mock_session)

    assert FeatureFlagsRepository._cache["TEST_FLAG_1"] is True
    assert FeatureFlagsRepository._cache["TEST_FLAG_2"] is False
    assert len(FeatureFlagsRepository._cache) == 2


@pytest.mark.asyncio
async def test_get_feature_flag_status_uses_cache():
    """It should use the cache and not hit the DB if the flag is cached."""
    FeatureFlagsRepository._cache[FeatureFlagNames.BOT.value] = True

    mock_session = AsyncMock(spec=AsyncSession)

    result = await FeatureFlagsRepository.get_feature_flag_status(
        mock_session, FeatureFlagNames.BOT
    )

    assert result is True
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_get_feature_flag_status_updates_cache_on_miss():
    """It should query DB on cache miss and update the cache."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = Mock()
    mock_result.one_or_none.return_value = (True,)
    mock_session.execute.return_value = mock_result

    assert FeatureFlagNames.BOT.value not in FeatureFlagsRepository._cache

    result = await FeatureFlagsRepository.get_feature_flag_status(
        mock_session, FeatureFlagNames.BOT
    )

    assert result is True
    mock_session.execute.assert_called_once()
    assert FeatureFlagsRepository._cache[FeatureFlagNames.BOT.value] is True


@pytest.mark.asyncio
async def test_update_feature_flag_updates_cache():
    """It should update the cache when a flag is modified."""
    mock_session = AsyncMock(spec=AsyncSession)

    FeatureFlagsRepository._cache["TEST_FLAG"] = False

    await FeatureFlagsRepository.update_feature_flag(mock_session, "TEST_FLAG", True)

    mock_session.execute.assert_called_once()
    mock_session.commit.assert_awaited_once()

    assert FeatureFlagsRepository._cache["TEST_FLAG"] is True
