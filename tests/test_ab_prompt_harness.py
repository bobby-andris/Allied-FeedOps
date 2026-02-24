from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_script_module(filename: str, module_name: str):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_json_payload_unwraps_content_wrapper() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_wrapper")
    parsed = harness.parse_json_payload(
        '{"content": {"google_title": "A", "google_short_title": "B", '
        '"google_description": "{FINISH_SENTENCE}"}}'
    )
    assert parsed["google_title"] == "A"
    assert parsed["google_short_title"] == "B"
    assert parsed["google_description"] == "{FINISH_SENTENCE}"


def test_build_user_prompt_google_uses_platform_specific_builder_contract(monkeypatch) -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_prompt_contract")

    monkeypatch.setattr(harness, "get_category_guidance", lambda _category: "")
    monkeypatch.setattr(
        harness,
        "format_gold_standard_examples_bundle",
        lambda max_examples=2: "",
    )

    parent = SimpleNamespace(
        master_sku="SKU-TEST",
        category="Towel Bars",
        collection="Skyline",
        current_title="24-Inch Wall Mount Towel Bar",
        current_description="Solid brass wall mounted towel bar.",
        bullet_1="Wall mounted",
        bullet_2="Solid brass",
        bullet_3=None,
        bullet_4=None,
        variants=[],
    )
    evidence = [
        SimpleNamespace(field="material", value="Brass", source="material"),
        SimpleNamespace(field="mounting_type", value="Wall Mounted", source="catalog"),
    ]

    prompt = harness.build_user_prompt(
        "google",
        parent,
        evidence,
        evidence_markdown="",
        finish_pairs=[],
    )

    assert "<task>Generate Google Shopping content for MasterSKU: SKU-TEST.</task>" in prompt
    assert "<evidence_table>" in prompt
    assert "Product Evidence Table:" not in prompt


def test_finish_platform_completion_budget_floor() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_budget")
    assert harness._platform_completion_tokens("finish", 4000) == 10000
    assert harness._platform_completion_tokens("google", 4000) == 4000


def test_should_escalate_budget_only_on_empty_length_responses() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_escalate")
    assert harness._should_escalate_budget(
        {"finish_reason": "length", "raw_content_chars": 0}
    )
    assert not harness._should_escalate_budget(
        {"finish_reason": "length", "raw_content_chars": 12}
    )
    assert not harness._should_escalate_budget(
        {"finish_reason": "stop", "raw_content_chars": 0}
    )


def test_evaluate_platform_output_ignores_claim_source_values() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_claims")
    payload = {
        "google_title": "{FINISH_NAME} Wall Mount Towel Bar - Allied Brass",
        "google_short_title": "{FINISH_NAME} Towel Bar",
        "google_description": (
            "Solid brass wall mount towel bar for coordinated bathroom design. "
            + ("x" * 680)
            + " {FINISH_SENTENCE}"
        ),
        "claims": [
            {
                "field": "bullet_1",
                "source_value": "made of the finest solid brass materials",
                "used_in": ["google_description"],
            }
        ],
        "self_score": {"overall": 8},
    }
    parent = SimpleNamespace(variants=[])

    checks = harness.evaluate_platform_output("google", payload, parent)
    assert checks["no_banned_words"]["passed"] is True
    assert checks["no_competitor_brands"]["passed"] is True


def test_evaluate_platform_output_enforces_towel_bar_noun_for_towel_bar_category() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_towel_bar_noun")
    payload = {
        "google_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Rack - Allied Brass",
        "google_short_title": "24-Inch Wall Mount Towel Rack",
        "google_description": ("x" * 700) + " {FINISH_SENTENCE}",
        "claims": [],
        "self_score": {"overall": 8},
    }
    parent = SimpleNamespace(category="Towel Bars", variants=[])

    checks = harness.evaluate_platform_output("google", payload, parent)
    assert checks["title_matches_category_product_noun"]["passed"] is False
    assert checks["short_title_matches_category_product_noun"]["passed"] is False


def test_evaluate_platform_output_flags_meta_search_commentary_and_metadata_dump() -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_meta_checks")
    payload = {
        "bing_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar - Allied Brass",
        "bing_description": (
            "If you're searching for a better option, this design stands out. "
            "UPC: 123456789012 and GTIN: 000111222333 are listed here. "
            + ("y" * 700)
            + " {FINISH_SENTENCE}"
        ),
        "claims": [],
        "self_score": {"overall": 7},
    }
    parent = SimpleNamespace(category="Towel Bars", variants=[])

    checks = harness.evaluate_platform_output("bing", payload, parent)
    assert checks["no_meta_search_commentary"]["passed"] is False
    assert checks["no_metadata_dump"]["passed"] is False


@pytest.mark.asyncio
async def test_run_platform_tests_continues_after_platform_error(monkeypatch) -> None:
    harness = _load_script_module("ab_prompt_test.py", "ab_prompt_test_resilience")

    parent = SimpleNamespace(
        master_sku="TEST-1",
        category="Towel Bars",
        collection="Carolina",
        current_title="Wall Mount Towel Bar",
        variants=[],
    )
    monkeypatch.setattr(harness, "load_parent_sku_from_supabase", lambda _sku: parent)
    monkeypatch.setattr(harness, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(harness, "format_evidence_markdown", lambda _rows: "| field | value | source |")
    monkeypatch.setattr(harness, "AsyncOpenAI", lambda api_key: object())
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def _fake_generate_per_platform(*, platform: str, **_kwargs):
        if platform == "google":
            raise TimeoutError("simulated timeout")
        if platform == "bing":
            return {
                "platform": "bing",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "cached_tokens": 0},
                "latency_sec": 0.1,
                "payload": {
                    "bing_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar - Allied Brass",
                    "bing_description": ("y" * 710) + " {FINISH_SENTENCE}",
                    "claims": [],
                    "self_score": {"overall": 8},
                },
                "diagnostics": {
                    "initial": {
                        "finish_reason": "stop",
                        "refusal": None,
                        "raw_content_chars": 800,
                    },
                    "repair": None,
                },
            }
        raise AssertionError(f"Unexpected platform in test: {platform}")

    monkeypatch.setattr(harness, "generate_per_platform", _fake_generate_per_platform)

    returned_parent, results = await harness.run_platform_tests(
        sku="TEST-1",
        selected_platforms=["google", "bing"],
        model="gpt-5.2",
        reasoning_effort="high",
        max_completion_tokens=1200,
    )

    assert returned_parent.master_sku == "TEST-1"
    assert "google" in results and "bing" in results
    assert "error" in results["google"]
    assert results["google"]["checks"]["generation_succeeded"]["passed"] is False
    assert "payload" in results["bing"]
