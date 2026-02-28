from __future__ import annotations

import pytest

from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.generation.tasks import build_task_prompt
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline import generator as gen


@pytest.mark.asyncio
async def test_generate_per_platform_uses_task_scoped_prompts(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def _fake_execute_generation_legacy_payload(**kwargs):
        captured.update(kwargs)
        return {
            "google_description": (
                "Wall-mounted towel bar copy. {FINISH_SENTENCE} "
                "Built from solid brass for daily use."
            ),
            "finish_sentences": {
                finish: f"{finish} complements this wall-mounted towel bar profile."
                for finish in gen.get_finish_list()
            },
            "prompt_hashes": {"google": "hash-google"},
            "system_prompts": {"google": "sys-google"},
            "user_prompts": {"google": "user-google"},
            "usage_by_platform": {
                "google": {"prompt_tokens": 100, "completion_tokens": 25},
                "finish": {"prompt_tokens": 40, "completion_tokens": 20},
            },
            "latency_by_platform": {"google": 120, "finish": 35},
            "parse_by_platform": {
                "google": {"parse_mode": "strict_json", "missing_keys": []},
                "finish": {"parse_mode": "strict_json", "missing_keys": []},
            },
            "retry_by_platform": {
                "google": {"attempt_count": 1, "json_decode_retries": 0},
                "finish": {"attempt_count": 1, "json_decode_retries": 0},
            },
        }

    monkeypatch.setattr(gen, "execute_generation_legacy_payload", _fake_execute_generation_legacy_payload)
    monkeypatch.setattr(gen, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(gen, "filter_evidence_for_copy_context", lambda rows: rows)
    monkeypatch.setattr(gen, "build_keyword_placement_plan", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gen, "format_keyword_placement_section", lambda _plan: "")
    monkeypatch.setattr(gen, "get_category_guidance", lambda _category: "")
    monkeypatch.setattr(gen, "format_gold_standard_examples_bundle", lambda max_examples=2: "")

    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="Current description",
        variants=[],
    )

    result = await gen.generate_per_platform(
        parent_sku=parent,
        provider=object(),
        prompt_version="v2",
        selected_platforms=("google", "finish"),
        selected_content_types=("description",),
        request_id="req-task-scoped-prompts",
    )

    assert result["google_description"].count("{FINISH_SENTENCE}") == 1
    assert captured["prompt_overrides"] is None
    assert captured["system_prompt_overrides"] is None


def test_build_task_prompt_uses_current_core_prompt_signature() -> None:
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="Current description",
        variants=[],
    )
    spec = TaskSpec(
        task_id="task-google-title",
        kind=GenerationTaskKind.TITLE,
        master_sku=parent.master_sku,
        platform="google",
        content_type="title",
        prompt_version="v2",
        request_id="req-task-prompt-signature",
        diagnostic_mode=False,
        cost_cap_usd=None,
    )

    prompt = build_task_prompt(
        spec,
        parent_sku=parent,
        evidence=[],
        evidence_markdown="No evidence available.",
    )

    assert "Task Output Contract:" in prompt
    assert "google_title" in prompt
    assert "google_short_title" in prompt
