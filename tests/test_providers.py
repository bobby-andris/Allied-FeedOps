# tests/test_providers.py
import base64
import pytest
from abc import ABC
from unittest.mock import AsyncMock, patch, MagicMock
from feedops.providers.base import LLMProvider, ImageInput
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


# Task 4.1b: Provider default model tests
def test_openai_provider_default_model():
    """OpenAI provider uses gpt-5.2 by default."""
    provider = OpenAIProvider(api_key="test-key")
    assert provider.name == "openai/gpt-5.2"


def test_gemini_provider_default_model():
    """Gemini provider uses gemini-3-flash-preview by default."""
    provider = GeminiProvider(api_key="test-key")
    assert provider.name == "gemini/gemini-3-flash-preview"


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


@pytest.mark.asyncio
async def test_openai_provider_includes_image_input():
    """OpenAI provider includes image input when provided."""
    provider = OpenAIProvider(api_key="test-key")
    image_input = ImageInput(
        data=b"image-bytes",
        mime_type="image/png",
        source_url="https://example.com/image.png",
    )

    mock_response = MagicMock()
    mock_response.output_text = '{"title": "Test Title"}'
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50

    with patch.object(provider.client.responses, 'create', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        await provider.generate("Test prompt", {"type": "object"}, image=image_input)

        _, kwargs = mock_create.call_args
        input_payload = kwargs["input"]
        assert input_payload[0]["role"] == "user"
        content = input_payload[0]["content"]
        assert content[0]["type"] == "input_text"
        assert content[0]["text"] == "Test prompt"
        assert content[1]["type"] == "input_image"
        image_url = content[1]["image_url"]
        prefix = f"data:{image_input.mime_type};base64,"
        assert image_url.startswith(prefix)
        assert base64.b64decode(image_url[len(prefix):]) == image_input.data


# Task 4.3: Gemini Provider Tests
@pytest.mark.asyncio
async def test_gemini_provider_generate_parses_json():
    """Gemini provider parses JSON from response."""
    provider = GeminiProvider(api_key="test-key")

    with patch.object(provider, '_call_api', new_callable=AsyncMock) as mock_api:
        mock_api.return_value = '{"title": "Test Title"}'
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"


@pytest.mark.asyncio
async def test_gemini_provider_includes_image_input():
    """Gemini provider includes image input when provided."""
    provider = GeminiProvider(api_key="test-key")
    image_input = ImageInput(
        data=b"image-bytes",
        mime_type="image/png",
        source_url="https://example.com/image.png",
    )
    mock_response = MagicMock()
    mock_response.text = '{"title": "Test Title"}'
    image_part = object()

    with patch("feedops.providers.gemini_provider.types.Part.from_bytes", return_value=image_part) as mock_part:
        with patch.object(provider.client.aio.models, 'generate_content', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            result = await provider.generate("Test prompt", {"type": "object"}, image=image_input)
            assert result["title"] == "Test Title"

            mock_part.assert_called_once_with(data=image_input.data, mime_type=image_input.mime_type)
            _, kwargs = mock_generate.call_args
            assert kwargs["contents"] == [
                "Test prompt\n\nRespond with valid JSON only, no markdown.",
                image_part,
            ]


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
