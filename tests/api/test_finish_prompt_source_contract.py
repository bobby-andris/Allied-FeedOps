from __future__ import annotations

import pytest

import feedops.api.main as api_main


@pytest.mark.asyncio
async def test_finish_sentence_generation_uses_finish_platform_prompt(monkeypatch) -> None:
    captured_call: dict[str, object] = {}
    logged_events: list[tuple[str, dict[str, object]]] = []

    async def _fake_generate_with_metrics(**kwargs):
        captured_call.update(kwargs)
        return {
            "finish_sentences": {
                finish: f"{finish} complements this profile."
                for finish in api_main.get_finish_list()
            }
        }

    def _fake_log_event(_logger, _level, event_name: str, **fields) -> None:
        logged_events.append((event_name, fields))

    monkeypatch.setattr(api_main, "_generate_with_metrics", _fake_generate_with_metrics)
    monkeypatch.setattr(api_main, "log_event", _fake_log_event)
    monkeypatch.setattr(
        api_main,
        "_build_finish_sentences_user_prompt",
        lambda **_kwargs: "finish-user-prompt",
    )
    monkeypatch.setattr(
        api_main,
        "get_platform_system_prompt",
        lambda platform: f"platform-system-{platform}",
    )

    content, finish_sentences = await api_main._enforce_finish_sentence_parity(
        provider=object(),
        content="Wall-mounted towel bar with solid brass construction.",
        master_sku="1031/18",
        platform="google",
        endpoint="regenerate",
    )

    assert captured_call["system_prompt"] == "platform-system-finish"
    assert "{FINISH_SENTENCE}" in content
    assert finish_sentences is not None
    assert len(finish_sentences) == len(api_main.get_finish_list())

    expected_hash = api_main._assembled_prompt_hash(
        "platform-system-finish",
        "finish-user-prompt",
    )
    request_events = [
        fields for event_name, fields in logged_events if event_name == "generation.finish_sentences.request"
    ]
    assert len(request_events) == 1
    event_fields = request_events[0]
    assert event_fields["system_prompt_source"] == "platform_finish"
    assert event_fields["prompt_hash_finish"] == expected_hash
