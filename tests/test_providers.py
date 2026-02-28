# tests/test_providers.py
import base64
from abc import ABC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feedops.providers.base import ImageInput, LLMProvider
from feedops.providers.factory import FallbackProvider, get_provider
from feedops.providers.gemini_provider import GeminiProvider
from feedops.providers.openai_provider import OpenAIProvider


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
    mock_response.choices[0].message.content = (
        '{"title": "Test Title", "description": "Test"}'
    )
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response
        result = await provider.generate("Test prompt", {"type": "object"})
        assert result["title"] == "Test Title"


@pytest.mark.asyncio
async def test_openai_provider_retries_on_invalid_json():
    """OpenAI provider retries when JSON is invalid."""
    provider = OpenAIProvider(api_key="test-key", max_retries=2)

    invalid_response = MagicMock()
    invalid_response.choices = [MagicMock()]
    invalid_response.choices[0].message.content = "not valid json"
    invalid_response.usage.prompt_tokens = 100
    invalid_response.usage.completion_tokens = 50

    valid_response = MagicMock()
    valid_response.choices = [MagicMock()]
    valid_response.choices[0].message.content = '{"title": "Fixed"}'
    valid_response.usage.prompt_tokens = 100
    valid_response.usage.completion_tokens = 50

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
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
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"title": "Test Title"}'
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response
        await provider.generate("Test prompt", {"type": "object"}, image=image_input)

        _, kwargs = mock_create.call_args
        messages = kwargs["messages"]
        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Test prompt"
        assert content[1]["type"] == "image_url"
        image_url = content[1]["image_url"]["url"]
        prefix = f"data:{image_input.mime_type};base64,"
        assert image_url.startswith(prefix)
        assert base64.b64decode(image_url[len(prefix) :]) == image_input.data


@pytest.mark.asyncio
async def test_openai_provider_health_check_uses_max_completion_tokens_for_gpt5():
    """OpenAI health check uses max_completion_tokens for gpt-5 models."""
    provider = OpenAIProvider(api_key="test-key", model="gpt-5.2")

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "pong"

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_response
        ok = await provider.health_check()
        assert ok is True

        _, kwargs = mock_create.call_args
        assert "max_completion_tokens" in kwargs
        assert "max_tokens" not in kwargs


# Task 4.3: Gemini Provider Tests
@pytest.mark.asyncio
async def test_gemini_provider_generate_parses_json():
    """Gemini provider parses JSON from response."""
    provider = GeminiProvider(api_key="test-key")

    with patch.object(provider, "_call_api", new_callable=AsyncMock) as mock_api:
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

    with patch(
        "feedops.providers.gemini_provider.types.Part.from_bytes",
        return_value=image_part,
    ) as mock_part:
        with patch.object(
            provider.client.aio.models, "generate_content", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = mock_response
            result = await provider.generate(
                "Test prompt", {"type": "object"}, image=image_input
            )
            assert result["title"] == "Test Title"

            mock_part.assert_called_once_with(
                data=image_input.data, mime_type=image_input.mime_type
            )
            _, kwargs = mock_generate.call_args
            assert kwargs["contents"] == [
                "Test prompt\n\nRespond with valid JSON only, no markdown.",
                image_part,
            ]


# Task 4.4: Provider Factory Tests
def test_get_provider_returns_openai_by_default():
    """Factory returns OpenAI provider when configured."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
        provider = get_provider()
        assert provider.name.startswith("openai/")


def test_get_provider_applies_hardened_default_retry_and_timeout_controls():
    """Factory defaults enforce bounded runtime behavior when env overrides are absent."""
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
        provider = get_provider()
        assert provider.max_retries == 1
        assert provider.max_total_seconds == 120
        assert provider.client.max_retries == 0
        assert provider.client.timeout is not None
        timeout_read = (
            provider.client.timeout.read
            if hasattr(provider.client.timeout, "read")
            else provider.client.timeout
        )
        assert float(timeout_read) == 45.0
        assert getattr(provider, "json_retry_max") == 1


def test_get_provider_uses_openai_model_env():
    """Factory uses model override when configured."""
    with patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "test-key", "FEEDOPS_OPENAI_MODEL": "gpt-4o"},
    ):
        provider = get_provider()
        assert provider.name == "openai/gpt-4o"
        assert provider.max_retries == 1
        assert provider.client.max_retries == 0


def test_get_provider_uses_diagnostic_model_when_enabled():
    """Diagnostic mode forces low-cost model selection for debugging."""
    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-key",
            "FEEDOPS_DIAGNOSTIC_MODE": "1",
            "FEEDOPS_DIAGNOSTIC_FORCE_LOW_COST_MODEL": "1",
            "FEEDOPS_DIAGNOSTIC_MODEL": "gpt-4.1-mini",
            "FEEDOPS_OPENAI_MODEL": "gpt-5.2",
        },
        clear=True,
    ):
        provider = get_provider()
        assert provider.name == "openai/gpt-4.1-mini"


def test_get_provider_falls_back_to_gemini():
    """Factory returns Gemini when OpenAI not configured."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=True):
        provider = get_provider()
        assert provider.name.startswith("gemini/")


def test_get_provider_force_fallback_returns_fallback_provider():
    """Factory can force primary+fallback chain when both keys are present."""
    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "openai-key",
            "GEMINI_API_KEY": "gemini-key",
            "FEEDOPS_FORCE_PROVIDER_FALLBACK": "1",
        },
        clear=True,
    ):
        provider = get_provider()
        assert isinstance(provider, FallbackProvider)
        assert provider.primary.name.startswith("openai/")
        assert provider.fallback.name.startswith("gemini/")


@pytest.mark.asyncio
async def test_fallback_provider_exposes_primary_metrics_on_success():
    """FallbackProvider forwards usage/parse/retry telemetry from primary success."""

    class StubProvider(LLMProvider):
        def __init__(self, name: str):
            self._name = name
            self._last_usage = {"prompt_tokens": 12, "completion_tokens": 34}
            self._last_parse_details = {"parse_mode": "strict_json", "missing_keys": []}
            self._last_retry_counts = {"attempt_count": 1, "json_decode_retries": 0}

        @property
        def name(self) -> str:
            return self._name

        @property
        def last_usage(self) -> dict[str, int]:
            return self._last_usage.copy()

        @property
        def last_parse_details(self) -> dict[str, object]:
            return self._last_parse_details.copy()

        @property
        def last_retry_counts(self) -> dict[str, int]:
            return self._last_retry_counts.copy()

        async def generate(
            self,
            prompt: str,
            schema: dict,
            image: ImageInput | None = None,
            system_prompt: str | None = None,
            reasoning_effort: str | None = None,
            max_completion_tokens: int | None = None,
        ) -> dict:
            return {"google_title": "ok"}

        async def health_check(self) -> bool:
            return True

    primary = StubProvider("primary")
    fallback = StubProvider("fallback")
    provider = FallbackProvider(primary=primary, fallback=fallback)
    payload = await provider.generate("prompt", {"type": "object"})
    assert payload["google_title"] == "ok"
    assert provider.last_usage == {"prompt_tokens": 12, "completion_tokens": 34}
    assert provider.last_parse_details["parse_mode"] == "strict_json"
    assert provider.last_retry_counts["attempt_count"] == 1


@pytest.mark.asyncio
async def test_fallback_provider_exposes_fallback_metrics_on_failover():
    """FallbackProvider forwards telemetry from fallback provider when failover occurs."""

    class FailingProvider(LLMProvider):
        @property
        def name(self) -> str:
            return "primary"

        async def generate(
            self,
            prompt: str,
            schema: dict,
            image: ImageInput | None = None,
            system_prompt: str | None = None,
            reasoning_effort: str | None = None,
            max_completion_tokens: int | None = None,
        ) -> dict:
            raise RuntimeError("primary failed")

        async def health_check(self) -> bool:
            return True

    class FallbackSuccessProvider(LLMProvider):
        def __init__(self) -> None:
            self._last_usage = {"prompt_tokens": 99, "completion_tokens": 7}
            self._last_parse_details = {"parse_mode": "substring_fallback", "missing_keys": []}
            self._last_retry_counts = {"attempt_count": 2, "json_decode_retries": 1}

        @property
        def name(self) -> str:
            return "fallback"

        @property
        def last_usage(self) -> dict[str, int]:
            return self._last_usage.copy()

        @property
        def last_parse_details(self) -> dict[str, object]:
            return self._last_parse_details.copy()

        @property
        def last_retry_counts(self) -> dict[str, int]:
            return self._last_retry_counts.copy()

        async def generate(
            self,
            prompt: str,
            schema: dict,
            image: ImageInput | None = None,
            system_prompt: str | None = None,
            reasoning_effort: str | None = None,
            max_completion_tokens: int | None = None,
        ) -> dict:
            return {"google_title": "ok"}

        async def health_check(self) -> bool:
            return True

    provider = FallbackProvider(primary=FailingProvider(), fallback=FallbackSuccessProvider())
    payload = await provider.generate("prompt", {"type": "object"})
    assert payload["google_title"] == "ok"
    assert provider.last_usage == {"prompt_tokens": 99, "completion_tokens": 7}
    assert provider.last_parse_details["parse_mode"] == "substring_fallback"
    assert provider.last_retry_counts["attempt_count"] == 2


def test_get_provider_raises_when_none_configured():
    """Factory raises when no provider configured."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="No LLM provider configured"):
            get_provider()
        with pytest.raises(ValueError, match="No LLM provider configured"):
            get_provider()


def test_get_provider_applies_retry_and_timeout_env_overrides():
    """Factory applies bounded retry/timeout controls for OpenAI provider."""
    with patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "test-key",
            "FEEDOPS_PROVIDER_MAX_RETRIES": "1",
            "FEEDOPS_OPENAI_SDK_MAX_RETRIES": "1",
            "FEEDOPS_OPENAI_SDK_TIMEOUT_SECONDS": "75",
            "FEEDOPS_PROVIDER_MAX_TOTAL_SECONDS": "180",
            "FEEDOPS_OPENAI_JSON_RETRY_MAX": "3",
        },
        clear=True,
    ):
        provider = get_provider()
        assert provider.max_retries == 1
        assert provider.max_total_seconds == 180
        assert provider.client.max_retries == 1
        assert getattr(provider, "json_retry_max") == 3
