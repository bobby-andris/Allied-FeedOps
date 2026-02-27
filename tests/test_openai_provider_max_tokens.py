import types

import pytest


@pytest.mark.asyncio
async def test_openai_provider_sets_max_completion_tokens_for_gpt5(monkeypatch):
    from feedops.providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(api_key="test", model="gpt-5.2")

    captured = {}

    async def _fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="{}"))],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)

    result = await provider.generate(prompt="{}", schema={})
    assert result == {}
    assert "max_completion_tokens" in captured
    assert captured["max_completion_tokens"] == 8000
    assert "max_tokens" not in captured


@pytest.mark.asyncio
async def test_openai_provider_enforces_max_total_seconds(monkeypatch):
    from feedops.providers.base import LLMError
    from feedops.providers.openai_provider import OpenAIProvider

    provider = OpenAIProvider(
        api_key="test",
        model="gpt-5.2",
        max_retries=2,
        max_total_seconds=0.0001,
    )

    async def _fake_create(**_kwargs):
        raise AssertionError("provider should stop before issuing API call")

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)

    with pytest.raises(LLMError, match="provider_max_total_seconds_exceeded"):
        await provider.generate(prompt="{}", schema={})
