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
