"""Regression tests for 5 known GPT-5.2 bugs (GPT-01 through GPT-05).

These tests lock down the critical fixes in openai_provider.py and prompts.py
so they cannot silently regress when someone edits those files.

Bug inventory:
  GPT-01: temperature=0.7 was always passed alongside reasoning_effort (mutually exclusive on GPT-5.2)
  GPT-02: FEEDOPS_REASONING_EFFORT env var unset → no reasoning sent (GPT-5.2 defaults to zero reasoning)
  GPT-03: Used legacy json_object mode instead of json_schema strict mode
  GPT-04: No prompt_cache_retention: "24h" in extra_body — cache expired in 5-10 min during batch runs
  GPT-05: System prompt used === headers instead of XML tags (GPT-5.2 parses XML better)
"""

import types

import pytest


def _make_fake_create(captured_dict: dict):
    """Return an async fake for client.chat.completions.create that captures kwargs."""

    async def _fake_create(**kwargs):
        captured_dict.update(kwargs)
        return types.SimpleNamespace(
            choices=[
                types.SimpleNamespace(
                    message=types.SimpleNamespace(content="{}"),
                    finish_reason="stop",
                )
            ],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    return _fake_create


@pytest.mark.asyncio
async def test_gpt01_temperature_not_passed_with_reasoning_effort(monkeypatch):
    """GPT-01: temperature and reasoning_effort are mutually exclusive on GPT-5.2.

    When reasoning_effort is set (either from env var or argument), temperature
    must NOT be included in the API call kwargs.
    """
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    await provider.generate(prompt="{}", schema={})

    assert "reasoning_effort" in captured, "reasoning_effort must be present in API call"
    assert "temperature" not in captured, (
        "temperature must NOT be passed when reasoning_effort is set "
        "(they are mutually exclusive on GPT-5.2)"
    )


@pytest.mark.asyncio
async def test_gpt02_reasoning_effort_defaults_to_high(monkeypatch):
    """GPT-02: When FEEDOPS_REASONING_EFFORT env var is unset, default is 'high'.

    Previously, an unset env var caused reasoning to be omitted entirely, meaning
    GPT-5.2 received zero reasoning budget. The fix defaults to 'high'.
    """
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    await provider.generate(prompt="{}", schema={})

    assert captured.get("reasoning_effort") == "high", (
        f"Expected reasoning_effort='high' when env var is unset, "
        f"got: {captured.get('reasoning_effort')!r}"
    )


@pytest.mark.asyncio
async def test_gpt02_reasoning_effort_respects_env_var(monkeypatch):
    """GPT-02 companion: env var value is honored when set.

    When FEEDOPS_REASONING_EFFORT is explicitly set, that value must be used.
    """
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.setenv("FEEDOPS_REASONING_EFFORT", "low")
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    await provider.generate(prompt="{}", schema={})

    assert captured.get("reasoning_effort") == "low", (
        f"Expected reasoning_effort='low' from env var, "
        f"got: {captured.get('reasoning_effort')!r}"
    )


@pytest.mark.asyncio
async def test_gpt03_json_schema_strict_mode(monkeypatch):
    """GPT-03: response_format uses json_schema with strict=True, not json_object.

    Previously used the legacy json_object mode which wastes tokens on retry loops
    when the response doesn't match the expected schema.
    """
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    # Use a schema with no properties so the fake "{}" response passes validation.
    # We only verify how response_format is constructed in the API call kwargs.
    # _build_strict_schema is called with the schema regardless of properties count.
    simple_schema = {"type": "object", "properties": {}}
    await provider.generate(prompt="{}", schema=simple_schema)

    response_format = captured.get("response_format", {})
    assert response_format.get("type") == "json_schema", (
        f"Expected response_format.type='json_schema', got: {response_format.get('type')!r}"
    )
    json_schema_block = response_format.get("json_schema", {})
    assert json_schema_block.get("strict") is True, (
        f"Expected json_schema.strict=True, got: {json_schema_block.get('strict')!r}"
    )


@pytest.mark.asyncio
async def test_gpt04_prompt_cache_retention_text_path(monkeypatch):
    """GPT-04: prompt_cache_retention='24h' present in extra_body for text generation.

    Without this, cache expires after 5-10 minutes — meaning back-to-back batch
    SKU calls don't benefit from prompt caching of the (large) system prompt.
    """
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    # Text path: no image argument
    await provider.generate(prompt="{}", schema={})

    extra_body = captured.get("extra_body", {})
    assert extra_body.get("prompt_cache_retention") == "24h", (
        f"Expected extra_body['prompt_cache_retention']='24h' on text path, "
        f"got: {extra_body!r}"
    )


@pytest.mark.asyncio
async def test_gpt04_prompt_cache_retention_image_path(monkeypatch):
    """GPT-04: prompt_cache_retention='24h' present in extra_body for image generation.

    Both text and image API call paths must include the cache retention header.
    The image path is a separate code branch in openai_provider.py.
    """
    from feedops.providers.base import ImageInput
    from feedops.providers.openai_provider import OpenAIProvider

    monkeypatch.delenv("FEEDOPS_REASONING_EFFORT", raising=False)
    provider = OpenAIProvider(api_key="test", model="gpt-5.2")
    captured = {}
    monkeypatch.setattr(provider.client.chat.completions, "create", _make_fake_create(captured))

    # Minimal 1x1 PNG bytes for image path
    minimal_png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    image = ImageInput(data=minimal_png, mime_type="image/png", source_url="test://img")

    await provider.generate(prompt="{}", schema={}, image=image)

    extra_body = captured.get("extra_body", {})
    assert extra_body.get("prompt_cache_retention") == "24h", (
        f"Expected extra_body['prompt_cache_retention']='24h' on image path, "
        f"got: {extra_body!r}"
    )


def test_gpt05_system_prompt_uses_xml_tags():
    """GPT-05: SYSTEM_PROMPT uses XML section tags, not === headers.

    GPT-5.2 parses XML structure better than === delimiters. All 5 expected
    XML section tags must be present, and === must not appear.
    """
    from feedops.pipeline.prompts import SYSTEM_PROMPT

    assert "===" not in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT must not contain '===' headers — use XML tags instead"
    )

    required_xml_tags = [
        "creative_direction",
        "objective_hierarchy",
        "brand_voice",
        "accuracy_guardrail",
        "output_contract",
    ]
    for tag in required_xml_tags:
        assert f"<{tag}>" in SYSTEM_PROMPT, (
            f"SYSTEM_PROMPT missing required XML tag: <{tag}>"
        )
