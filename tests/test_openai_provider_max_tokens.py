import types

import pytest
import asyncio


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

    calls = {"count": 0}
    provider = OpenAIProvider(
        api_key="test",
        model="gpt-5.2",
        max_retries=3,
        max_total_seconds=0.05,
    )

    async def _fake_create(**_kwargs):
        calls["count"] += 1
        await asyncio.sleep(0.06)
        raise RuntimeError("request timeout")

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)

    with pytest.raises(LLMError, match="provider_max_total_seconds_exceeded"):
        await provider.generate(prompt="{}", schema={})
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_openai_provider_enforces_json_retry_budget(monkeypatch):
    from feedops.providers.base import LLMError
    from feedops.providers.openai_provider import OpenAIProvider

    calls = {"count": 0}
    provider = OpenAIProvider(
        api_key="test",
        model="gpt-5.2",
        max_retries=4,
        json_retry_max=1,
    )

    async def _fake_create(**_kwargs):
        calls["count"] += 1
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="not-json"))],
            usage={"prompt_tokens": 2, "completion_tokens": 1},
        )

    monkeypatch.setattr(provider.client.chat.completions, "create", _fake_create)

    with pytest.raises(LLMError, match="json_retry_budget_exceeded") as exc_info:
        await provider.generate(prompt="{}", schema={})

    # Initial attempt + one JSON repair retry.
    assert calls["count"] == 2
    assert exc_info.value.retries == 2
