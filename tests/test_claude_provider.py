"""Tests for ClaudeProvider against all 3 content platforms.

Tests verify:
- ClaudeProvider instantiation and name property
- generate() returns parsed JSON for Google, Bing, and Shopify platform schemas
- output_config.format with json_schema type passed to Anthropic API
- cache_control={"type": "ephemeral"} passed to API
- System prompt passed as system= kwarg (not in messages list)
- Image input uses Anthropic base64 source format
- JSON retry logic on parse failures
- LLMError raised after max_retries exhausted
- Usage extraction mapping (Anthropic -> standard dict)
- health_check returns True/False correctly
- aclose() calls client.close()
- reasoning_effort accepted without error but not forwarded to API
- Circuit breaker blocks when open
"""

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from feedops.providers.base import ImageInput, LLMError
from feedops.providers.claude_provider import ClaudeProvider, _extract_claude_usage
from feedops.providers.reliability import circuit_breakers


# ---- Schema fixtures ----

GOOGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "google_title": {"type": "string"},
        "google_description": {"type": "string"},
    },
}

BING_SCHEMA = {
    "type": "object",
    "properties": {
        "bing_title": {"type": "string"},
        "bing_description": {"type": "string"},
    },
}

SHOPIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "shopify_title": {"type": "string"},
        "shopify_description": {"type": "string"},
    },
}


# ---- Helper ----

def _mock_claude_response(
    text: str,
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read: int = 0,
) -> MagicMock:
    """Build a MagicMock mimicking the Anthropic response shape.

    response.content[0].text  — text content
    response.usage.input_tokens / output_tokens / cache_read_input_tokens
    """
    mock_block = MagicMock()
    mock_block.text = text

    mock_usage = MagicMock()
    mock_usage.input_tokens = input_tokens
    mock_usage.output_tokens = output_tokens
    mock_usage.cache_read_input_tokens = cache_read

    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_response.usage = mock_usage

    return mock_response


# ---- Autouse fixture: reset circuit breaker before each test ----

@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    circuit_breakers.reset()
    yield
    circuit_breakers.reset()


# ---- Instantiation tests ----

def test_claude_provider_default_model():
    """ClaudeProvider name uses claude-sonnet-4-6 by default."""
    provider = ClaudeProvider(api_key="test-key")
    assert provider.name == "claude/claude-sonnet-4-6"


def test_claude_provider_custom_model():
    """ClaudeProvider name reflects custom model string."""
    provider = ClaudeProvider(api_key="test-key", model="claude-opus-4-6")
    assert provider.name == "claude/claude-opus-4-6"


# ---- Platform schema tests ----

async def test_claude_provider_generate_google_schema():
    """generate() returns parsed JSON with Google platform fields."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "Allied Brass Grab Bar", "google_description": "Polished Chrome"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        result = await provider.generate("Test prompt", GOOGLE_SCHEMA)

    assert result["google_title"] == "Allied Brass Grab Bar"
    assert result["google_description"] == "Polished Chrome"


async def test_claude_provider_generate_bing_schema():
    """generate() returns parsed JSON with Bing platform fields."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"bing_title": "Bing Title", "bing_description": "Bing Desc"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        result = await provider.generate("Test prompt", BING_SCHEMA)

    assert result["bing_title"] == "Bing Title"
    assert result["bing_description"] == "Bing Desc"


async def test_claude_provider_generate_shopify_schema():
    """generate() returns parsed JSON with Shopify platform fields."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"shopify_title": "Shopify Title", "shopify_description": "Shopify Desc"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        result = await provider.generate("Test prompt", SHOPIFY_SCHEMA)

    assert result["shopify_title"] == "Shopify Title"
    assert result["shopify_description"] == "Shopify Desc"


# ---- API call structure tests ----

async def test_claude_provider_passes_output_config():
    """generate() passes output_config.format with json_schema type to Anthropic API."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA)

    _, kwargs = mock_create.call_args
    output_config = kwargs["output_config"]
    assert output_config["format"]["type"] == "json_schema"
    assert output_config["format"]["schema"] == GOOGLE_SCHEMA


async def test_claude_provider_passes_cache_control():
    """generate() passes cache_control={"type": "ephemeral"} to Anthropic API."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA)

    _, kwargs = mock_create.call_args
    assert kwargs["cache_control"] == {"type": "ephemeral"}


async def test_claude_provider_system_prompt_as_kwarg():
    """System prompt is passed as system= kwarg, NOT as a message in messages list."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)
    system_text = "You are a product content expert."

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA, system_prompt=system_text)

    _, kwargs = mock_create.call_args
    # system= kwarg must be set
    assert kwargs["system"] == system_text
    # No system message in messages list
    messages = kwargs["messages"]
    for msg in messages:
        assert msg.get("role") != "system"


async def test_claude_provider_no_system_kwarg_when_not_provided():
    """When system_prompt is None, system= kwarg must not appear in the API call."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA)

    _, kwargs = mock_create.call_args
    assert "system" not in kwargs


# ---- Image input test ----

async def test_claude_provider_image_input():
    """Image input uses Anthropic base64 source format (type=image, source.type=base64)."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)
    img_data = b"fake-image-bytes"
    image = ImageInput(data=img_data, mime_type="image/png", source_url="http://example.com/img.png")

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA, image=image)

    _, kwargs = mock_create.call_args
    messages = kwargs["messages"]
    assert len(messages) == 1
    content_blocks = messages[0]["content"]
    # Find the image block
    image_blocks = [b for b in content_blocks if b.get("type") == "image"]
    assert len(image_blocks) == 1
    img_block = image_blocks[0]
    assert img_block["source"]["type"] == "base64"
    assert img_block["source"]["media_type"] == "image/png"
    assert img_block["source"]["data"] == base64.b64encode(img_data).decode("utf-8")


# ---- Retry logic tests ----

async def test_claude_provider_retries_on_invalid_json():
    """generate() retries on invalid JSON and succeeds on second attempt."""
    provider = ClaudeProvider(api_key="test-key", max_retries=2, json_retry_max=2)
    invalid_resp = _mock_claude_response("not valid json at all")
    valid_resp = _mock_claude_response(
        json.dumps({"google_title": "Fixed", "google_description": "Done"})
    )

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = [invalid_resp, valid_resp]
        result = await provider.generate("Test prompt", GOOGLE_SCHEMA)

    assert result["google_title"] == "Fixed"
    assert mock_create.call_count == 2


async def test_claude_provider_raises_after_max_retries():
    """generate() raises LLMError after all retries return invalid JSON."""
    provider = ClaudeProvider(api_key="test-key", max_retries=2, json_retry_max=5)
    invalid_resp = _mock_claude_response("not valid json")

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = invalid_resp
        with pytest.raises(LLMError):
            await provider.generate("Test prompt", GOOGLE_SCHEMA)


# ---- Usage extraction tests ----

async def test_claude_provider_usage_extraction():
    """last_usage maps Anthropic field names to standard dict after successful generate."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload, input_tokens=100, output_tokens=50, cache_read=0)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA)

    assert provider.last_usage == {"prompt_tokens": 100, "completion_tokens": 50, "cached_tokens": 0}


async def test_claude_provider_usage_with_cache_hit():
    """last_usage reflects cache_read_input_tokens as cached_tokens."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload, input_tokens=200, output_tokens=60, cache_read=80)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        await provider.generate("Test prompt", GOOGLE_SCHEMA)

    assert provider.last_usage["cached_tokens"] == 80


# ---- _extract_claude_usage unit tests ----

def test_extract_claude_usage_standard():
    """_extract_claude_usage correctly maps Anthropic usage fields."""
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.usage.cache_read_input_tokens = 30

    result = _extract_claude_usage(mock_response)
    assert result == {"prompt_tokens": 100, "completion_tokens": 50, "cached_tokens": 30}


def test_extract_claude_usage_no_cache():
    """_extract_claude_usage returns 0 cached_tokens when cache_read_input_tokens is 0."""
    mock_response = MagicMock()
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.usage.cache_read_input_tokens = 0

    result = _extract_claude_usage(mock_response)
    assert result == {"prompt_tokens": 100, "completion_tokens": 50, "cached_tokens": 0}


def test_extract_claude_usage_no_usage_attr():
    """_extract_claude_usage returns zeros when response has no usage attr."""
    mock_response = MagicMock(spec=[])  # no attributes
    result = _extract_claude_usage(mock_response)
    assert result == {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}


# ---- health_check tests ----

async def test_claude_provider_health_check_success():
    """health_check returns True when API call succeeds."""
    provider = ClaudeProvider(api_key="test-key")
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        result = await provider.health_check()

    assert result is True


async def test_claude_provider_health_check_failure():
    """health_check returns False when API raises an exception."""
    provider = ClaudeProvider(api_key="test-key")

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.side_effect = Exception("API unavailable")
        result = await provider.health_check()

    assert result is False


# ---- aclose test ----

async def test_claude_provider_aclose():
    """aclose() calls client.close()."""
    provider = ClaudeProvider(api_key="test-key")

    with patch.object(provider.client, "close", new_callable=AsyncMock) as mock_close:
        await provider.aclose()

    mock_close.assert_awaited_once()


# ---- reasoning_effort test ----

async def test_claude_provider_accepts_reasoning_effort():
    """reasoning_effort parameter is accepted without error, not forwarded to Anthropic API."""
    provider = ClaudeProvider(api_key="test-key")
    payload = json.dumps({"google_title": "T", "google_description": "D"})
    mock_resp = _mock_claude_response(payload)

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_resp
        # Should not raise
        await provider.generate("Test prompt", GOOGLE_SCHEMA, reasoning_effort="high")

    _, kwargs = mock_create.call_args
    # reasoning_effort and thinking must NOT be in the API call kwargs
    assert "reasoning_effort" not in kwargs
    assert "thinking" not in kwargs


# ---- Circuit breaker test ----

async def test_claude_provider_circuit_breaker_blocks():
    """LLMError with 'Circuit breaker open' raised when circuit is open."""
    provider = ClaudeProvider(api_key="test-key")
    # Force circuit open: record enough failures to trip the breaker
    provider_name = provider.name
    from feedops.providers.reliability import circuit_failure_threshold
    threshold = circuit_failure_threshold()
    for _ in range(threshold):
        circuit_breakers.record_failure(provider_name)

    with pytest.raises(LLMError, match="Circuit breaker open"):
        await provider.generate("Test prompt", GOOGLE_SCHEMA)


# ---- Property interface tests ----

def test_claude_provider_last_usage_returns_copy():
    """last_usage returns a copy of the internal dict."""
    provider = ClaudeProvider(api_key="test-key")
    usage = provider.last_usage
    usage["prompt_tokens"] = 999
    assert provider.last_usage["prompt_tokens"] == 0  # internal unchanged


def test_claude_provider_last_parse_details_returns_copy():
    """last_parse_details returns a copy of the internal dict."""
    provider = ClaudeProvider(api_key="test-key")
    details = provider.last_parse_details
    assert "parse_mode" in details


def test_claude_provider_last_retry_counts_returns_copy():
    """last_retry_counts returns a copy of the internal dict."""
    provider = ClaudeProvider(api_key="test-key")
    counts = provider.last_retry_counts
    assert "attempt_count" in counts
    assert "json_decode_retries" in counts
    assert "api_retries" in counts
    assert "budget_retries" in counts
