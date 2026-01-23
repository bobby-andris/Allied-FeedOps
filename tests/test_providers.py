# tests/test_providers.py
import pytest
from abc import ABC
from unittest.mock import AsyncMock, patch, MagicMock
from feedops.providers.base import LLMProvider
from feedops.providers.openai_provider import OpenAIProvider
from feedops.providers.gemini_provider import GeminiProvider
from feedops.providers.factory import get_provider


# Task 4.1: Base LLM Provider Tests
def test_llm_provider_is_abstract():
    """LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        LLMProvider()


def test_llm_provider_requires_generate_method():
    """LLMProvider subclass must implement generate."""
    class IncompleteProvider(LLMProvider):
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IncompleteProvider()


# Task 4.2: OpenAI Provider Tests
@pytest.mark.asyncio
async def test_openai_provider_generate_parses_json():
    """OpenAI provider parses JSON from response."""
    provider = OpenAIProvider(api_key="test-key")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"title": "Test Title", "description": "Test"}'
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"


@pytest.mark.asyncio
async def test_openai_provider_retries_on_invalid_json():
    """OpenAI provider retries when JSON is invalid."""
    provider = OpenAIProvider(api_key="test-key", max_retries=2)

    invalid_response = MagicMock()
    invalid_response.choices = [MagicMock()]
    invalid_response.choices[0].message.content = 'not valid json'
    invalid_response.usage.prompt_tokens = 100
    invalid_response.usage.completion_tokens = 50

    valid_response = MagicMock()
    valid_response.choices = [MagicMock()]
    valid_response.choices[0].message.content = '{"title": "Fixed"}'
    valid_response.usage.prompt_tokens = 100
    valid_response.usage.completion_tokens = 50

    with patch.object(provider.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = [invalid_response, valid_response]
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Fixed"
        assert mock_create.call_count == 2


# Task 4.3: Gemini Provider Tests
@pytest.mark.asyncio
async def test_gemini_provider_generate_parses_json():
    """Gemini provider parses JSON from response."""
    provider = GeminiProvider(api_key="test-key")

    with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_api:
        mock_api.return_value = '{"title": "Test Title"}'
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"


# Task 4.4: Provider Factory Tests
def test_get_provider_returns_openai_by_default():
    """Factory returns OpenAI provider when configured."""
    with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
        provider = get_provider()
        assert provider.name.startswith("openai/")


def test_get_provider_falls_back_to_gemini():
    """Factory returns Gemini when OpenAI not configured."""
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}, clear=True):
        provider = get_provider()
        assert provider.name.startswith("gemini/")


def test_get_provider_raises_when_none_configured():
    """Factory raises when no provider configured."""
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError, match="No LLM provider configured"):
            get_provider()
