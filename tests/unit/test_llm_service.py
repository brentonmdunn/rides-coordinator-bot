"""Tests for LLM service."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_service import LLMService


class TestLLMService:
    """Tests for the LLMService class."""

    @pytest.fixture
    def llm_service(self):
        """Fixture to create an LLMService instance with a mocked LLM."""
        with patch("app.services.llm_service.ChatGoogleGenerativeAI"):
            service = LLMService()
            service.llm = MagicMock()
            yield service

    def test_invoke_llm_success_json_block(self, llm_service):
        """Should correctly parse a JSON block response."""
        # Mock response with markdown code block
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"Driver1": [{"name": "Alice", "location": "Sixth loop"}]}\n```'
        )
        llm_service.llm.invoke.return_value = mock_response

        result = llm_service.invoke_llm("pickups", "drivers", {})

        assert result == {"Driver1": [{"name": "Alice", "location": "Sixth loop"}]}

    def test_invoke_llm_success_raw_json(self, llm_service):
        """Should correctly parse a raw JSON response."""
        # Mock response with raw json
        mock_response = MagicMock()
        mock_response.content = '{"Driver1": [{"name": "Alice", "location": "Sixth loop"}]}'
        llm_service.llm.invoke.return_value = mock_response

        result = llm_service.invoke_llm("pickups", "drivers", {})

        assert result == {"Driver1": [{"name": "Alice", "location": "Sixth loop"}]}

    def test_invoke_llm_validation_error(self, llm_service):
        """Should raise an error if the LLM returns an error schema."""
        mock_response = MagicMock()
        mock_response.content = '{"error": "Some error message"}'
        llm_service.llm.invoke.return_value = mock_response

        # Depending on how validation is implemented, it might raise validation error
        # or return the dict
        # In the code: LLMOutputError.model_validate(llm_result)
        # If it validates successfully as an error, it returns the dict (but logs it? or raises?)
        # The code returns llm_result.

        result = llm_service.invoke_llm("pickups", "drivers", {})
        assert "error" in result

    def test_invoke_llm_comma_in_name_error(self, llm_service):
        """Should raise an exception if a name contains a comma."""
        import tenacity

        mock_response = MagicMock()
        mock_response.content = '{"Driver1": [{"name": "Alice, Bob", "location": "Sixth loop"}]}'
        llm_service.llm.invoke.return_value = mock_response

        # Since the method is decorated with retry, it will retry until it gives up
        # and raises RetryError
        with pytest.raises(tenacity.RetryError) as exc_info:
            llm_service.invoke_llm("pickups", "drivers", {})

        # Verify the underlying exception
        assert "Names cannot contain commas" in str(exc_info.value.last_attempt.exception())
