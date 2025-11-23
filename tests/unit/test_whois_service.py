from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.engine import Row

from app.services.whois_service import WhoisService


# Helper setup for Mocking Rows with attribute access
def create_mock_row(name: str, discord_username: str) -> Mock:
    mock_row = Mock(spec=Row)
    # Patch the attributes used in the service layer
    mock_row.name = name
    mock_row.discord_username = discord_username
    return mock_row


@pytest.mark.asyncio
@patch("app.services.whois_service.WhoisRepo")
@patch("app.services.whois_service.AsyncSessionLocal")
async def test_get_whois_data_found(mock_async_session_local, mock_whois_repo):
    """Tests the service formats multiple results correctly."""
    # Arrange
    test_name = "brenton"

    # 1. Setup mock repository data
    mock_data = [
        create_mock_row("Brenton Dunn", "brentond"),
        create_mock_row("Brenton Smith", "smithb"),
    ]
    mock_whois_repo.fetch_data_by_name = AsyncMock(return_value=mock_data)

    # 2. Setup mock session context manager
    # The session needs to be an object that the async with statement can use
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_async_session_local.return_value = mock_session

    expected_output = (
        "**Name:** Brenton Dunn\n**Discord:** brentond"
        "\n---\n"
        "**Name:** Brenton Smith\n**Discord:** smithb"
    )

    # Act
    result = await WhoisService.get_whois_data(test_name)

    # Assert
    assert result == expected_output
    mock_whois_repo.fetch_data_by_name.assert_called_once_with(mock_session, test_name)
    # Check that the session context manager was entered and exited
    mock_session.__aenter__.assert_called_once()
    mock_session.__aexit__.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.whois_service.WhoisRepo")
@patch("app.services.whois_service.AsyncSessionLocal")
async def test_get_whois_data_not_found(mock_async_session_local, mock_whois_repo):
    """Tests the service returns None when no results are found."""
    # Arrange
    test_name = "nomatch"
    mock_whois_repo.fetch_data_by_name = AsyncMock(return_value=[])

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_async_session_local.return_value = mock_session

    # Act
    result = await WhoisService.get_whois_data(test_name)

    # Assert
    assert result is None
    mock_whois_repo.fetch_data_by_name.assert_called_once()
