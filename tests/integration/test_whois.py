from unittest.mock import AsyncMock, Mock, patch

import pytest
from discord.ext import commands

from app.cogs.whois import Whois

# tests/integration/test_whois.py


# REMOVE 'from app.cogs.whois import Whois' from the top-level imports here!


@pytest.mark.asyncio
@patch("app.cogs.whois.WhoisService")
@patch("app.cogs.whois.feature_flag_enabled", lambda f: f)  # Now this will exist before import
@patch("app.cogs.whois.log_cmd", lambda f: f)
async def test_whois_command_match_found(mock_whois_service):
    """Tests the Discord command when the service returns data."""

    # --- LAZY IMPORT FIX ---
    # Import here so the class is defined WHILE the patches above are active.
    from app.cogs.whois import Whois
    # -----------------------

    # Arrange
    mock_bot = Mock(spec=commands.Bot)
    cog = Whois(mock_bot)

    # Mocking interaction.data
    mock_interaction_data = Mock()
    mock_interaction_data.get.side_effect = lambda key, default=None: {
        "name": "whois",
        "options": [{"name": "name", "value": "brenton"}],
        "user": Mock(),
        "channel": Mock(),
    }.get(key, default)

    mock_interaction = AsyncMock()
    mock_interaction.data = mock_interaction_data

    test_name = "brenton"
    mock_response = "**Name:** B.Dunn\n**Discord:** bdunn"
    mock_whois_service.get_whois_data = AsyncMock(return_value=mock_response)

    # Act
    await cog.whois.callback(cog, mock_interaction, name=test_name)

    # Assert
    mock_whois_service.get_whois_data.assert_called_once_with(test_name)


@pytest.mark.asyncio
@patch("app.cogs.whois.WhoisService")
@patch("app.cogs.whois.feature_flag_enabled", lambda f: f)
@patch("app.cogs.whois.log_cmd", lambda f: f)
async def test_whois_command_no_match(mock_whois_service):
    """Tests the Discord command when the service returns None (no match)."""
    # Arrange
    mock_bot = Mock(spec=commands.Bot)
    cog = Whois(mock_bot)

    # --- FIX: Mocking interaction.data to be a synchronous dictionary ---
    mock_interaction_data = Mock()
    mock_interaction_data.get.side_effect = lambda key, default=None: {
        "name": "whois",
        "options": [{"name": "name", "value": "nomatch"}],
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
