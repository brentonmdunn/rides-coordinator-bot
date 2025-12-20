from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.models import Locations as LocationsModel
from bot.repositories.whois_repo import WhoisRepo


@patch("bot.repositories.whois_repo.select")
@pytest.mark.asyncio
async def test_fetch_data_by_name_found(mock_select):  # Renamed to mock_select
    """Tests the repository returns data when matches are found."""
    # Arrange
    test_name = "brenton"

    # 1. Mock the final statement object and its methods (where and execute)
    # We still need a deep mock to simulate the entire chain:
    # select().where()...
    mock_stmt = Mock()
    mock_stmt.where.return_value = mock_stmt  # Chaining for .where()

    mock_select.return_value = mock_stmt

    # 2. Mock the final execution result
    mock_row1 = Mock(spec=Row)
    mock_row1.name = "Brenton Dunn"
    mock_row1.discord_username = "brentond"

    mock_result = Mock()
    mock_result.all = Mock(return_value=[mock_row1])

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    results = await WhoisRepo.fetch_data_by_name(mock_session, test_name)

    # Assert
    # 1. Assert that the select function was called with the correct columns
    mock_select.assert_called_once_with(LocationsModel.name, LocationsModel.discord_username)

    # 2. Assert that execute was called on the final statement object
    mock_session.execute.assert_called_once_with(mock_stmt)

    # 3. Assert final results are correct
    assert len(results) == 1
    assert results[0].name == "Brenton Dunn"


# --- Test Case 2 ---
@patch("bot.repositories.whois_repo.select")
@pytest.mark.asyncio
async def test_fetch_data_by_name_not_found(mock_select):  # Renamed to mock_select
    """Tests the repository returns an empty list when no matches are found."""
    # Arrange
    test_name = "nomatch"

    mock_stmt = Mock()
    mock_stmt.where.return_value = mock_stmt
    mock_select.return_value = mock_stmt

    # Mock the result object to return an empty list
    mock_result = Mock()
    mock_result.all = Mock(return_value=[])

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    results = await WhoisRepo.fetch_data_by_name(mock_session, test_name)

    # Assert
    mock_select.assert_called_once_with(LocationsModel.name, LocationsModel.discord_username)
    mock_session.execute.assert_called_once_with(mock_stmt)
    assert results == []
    assert isinstance(results, list)
