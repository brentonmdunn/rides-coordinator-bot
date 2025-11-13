import pytest
from unittest.mock import AsyncMock, Mock, patch
from app.cogs.whois import Whois
from discord.ext import commands


@pytest.mark.asyncio
@patch('app.cogs.whois.WhoisService')
@patch('app.cogs.whois.feature_flag_enabled', lambda f: f) # Bypass the feature flag decorator
@patch('app.cogs.whois.log_cmd', lambda f: f) # Bypass the logger decorator
async def test_whois_command_match_found(mock_whois_service):
    """Tests the Discord command when the service returns data."""
    # Arrange
    mock_bot = Mock(spec=commands.Bot) 
    cog = Whois(mock_bot)
    
    # --- FIX: Mocking interaction.data to be a synchronous dictionary ---
    mock_interaction_data = Mock()
    # Mock the .get() method to return the expected dictionary structure
    mock_interaction_data.get.side_effect = lambda key, default=None: {
        "name": "whois",
        # Provide a synchronous list for "options" to be iterated over in the decorator/logger
        "options": [
            {"name": "name", "value": "brenton"}
        ],
        "user": Mock(), # Mock for interaction.user access in logger/checks
        "channel": Mock(), # Mock for interaction.channel access
    }.get(key, default)

    mock_interaction = AsyncMock()
    mock_interaction.data = mock_interaction_data
    # ------------------------------------------------------------------
    
    test_name = "brenton"
    
    # Mock the service to return a formatted string
    mock_response = "**Name:** B.Dunn\n**Discord:** bdunn"
    mock_whois_service.get_whois_data = AsyncMock(return_value=mock_response)

    # Act
    # ACCESS THE ORIGINAL METHOD VIA .callback AND PASS self (cog) MANUALLY
    await cog.whois.callback(cog, mock_interaction, name=test_name)

    # Assert
    mock_whois_service.get_whois_data.assert_called_once_with(test_name)
    # Check that the correct response was sent
    mock_interaction.response.send_message.assert_called_once_with(mock_response)


@pytest.mark.asyncio
@patch('app.cogs.whois.WhoisService')
@patch('app.cogs.whois.feature_flag_enabled', lambda f: f)
@patch('app.cogs.whois.log_cmd', lambda f: f)
async def test_whois_command_no_match(mock_whois_service):
    """Tests the Discord command when the service returns None (no match)."""
    # Arrange
    mock_bot = Mock(spec=commands.Bot)
    cog = Whois(mock_bot)

    # --- FIX: Mocking interaction.data to be a synchronous dictionary ---
    mock_interaction_data = Mock()
    mock_interaction_data.get.side_effect = lambda key, default=None: {
        "name": "whois",
        "options": [
            {"name": "name", "value": "nomatch"}
        ],
        "user": Mock(),
        "channel": Mock(),
    }.get(key, default)
    
    mock_interaction = AsyncMock()
    mock_interaction.data = mock_interaction_data
    # ------------------------------------------------------------------

    test_name = "nomatch"
    
    # Mock the service to return None
    mock_whois_service.get_whois_data = AsyncMock(return_value=None)

    # Act
    # ACCESS THE ORIGINAL METHOD VIA .callback AND PASS self (cog) MANUALLY
    await cog.whois.callback(cog, mock_interaction, name=test_name)

    # Assert
    mock_whois_service.get_whois_data.assert_called_once_with(test_name)
    # Check that the "No matches found." message was sent
    mock_interaction.response.send_message.assert_called_once_with("No matches found.")