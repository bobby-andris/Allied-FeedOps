from __future__ import annotations

import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from feedops.models.parent_sku import ParentSKU
from feedops.api.prompt_builder import get_prompt_experiment_variant
from feedops.providers.factory import FallbackProvider
from feedops.providers.openai_provider import _parse_json_payload
from feedops.quality.evaluator import (
    PromptEvalRecord,
    build_prompt_eval_record,
    summarize_prompt_eval_records,
)


def _load_script_module(filename: str, module_name: str):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_phase28_root_cause_eval_script_loads() -> None:
    _load_script_module("phase28_root_cause_eval.py", "phase28_root_cause_eval_script")


def test_phase28_root_cause_eval_dry_run_cli() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "scripts" / "phase28_root_cause_eval.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dry-run",
            "--screening",
            "--sku-limit",
            "4",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Phase 28 evaluation run:" in completed.stdout


def test_phase28_root_cause_eval_dry_run_canonicalizes_unknown_variants() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "scripts" / "phase28_root_cause_eval.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--dry-run",
            "--screening",
            "--sku-limit",
            "4",
            "--variants",
            "control,totally-unknown",
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "variants=['control']" in completed.stdout


def test_prompt_experiment_variant_defaults_to_control(monkeypatch) -> None:
    monkeypatch.delenv("FEEDOPS_PROMPT_EXPERIMENT_VARIANT", raising=False)
    assert get_prompt_experiment_variant() == "control"


def test_prompt_experiment_variant_unknown_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("FEEDOPS_PROMPT_EXPERIMENT_VARIANT", "totally-unknown")
    assert get_prompt_experiment_variant() == "control"


def test_parse_json_payload_missing_required_keys_raises_parse_failure() -> None:
    parse_details: dict[str, object] = {}
    with pytest.raises(json.JSONDecodeError):
        _parse_json_payload(
            "```json\n{\"google_title\":\"T\"}\n```",
            expected_keys={"google_title", "google_description"},
            parse_details=parse_details,
        )
    assert parse_details["parse_mode"] == "markdown_fence"
    assert parse_details["missing_keys"] == ["google_description"]
    assert parse_details["parsed_key_count"] == 1
    assert parse_details["expected_key_count"] == 2


def test_parse_json_payload_emits_substring_fallback_parse_details() -> None:
    parse_details: dict[str, object] = {}
    payload = _parse_json_payload(
        "prefix {\"bing_title\":\"B\",\"bing_description\":\"Body\"} suffix",
        expected_keys={"bing_title", "bing_description"},
        parse_details=parse_details,
    )
    assert payload["bing_title"] == "B"
    assert parse_details["parse_mode"] == "substring_fallback"
    assert parse_details["missing_keys"] == []
    assert parse_details["parsed_key_count"] == 2
    assert parse_details["expected_key_count"] == 2


def test_prompt_eval_record_contract_and_placeholder_integrity_google() -> None:
    record = build_prompt_eval_record(
        run_id="run-1",
        sku="1016",
        platform="google",
        variant="control",
        prompt_hash="p-hash",
        schema_hash="s-hash",
        usage={"prompt_tokens": 10, "completion_tokens": 20},
        parse_details={
            "parse_mode": "strict_json",
            "missing_keys": [],
        },
        payload={
            "google_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar",
            "google_description": "Benefit-led copy here. {FINISH_SENTENCE}",
        },
        policy_violations=[],
    )
    assert isinstance(record, PromptEvalRecord)
    assert record.run_id == "run-1"
    assert record.platform == "google"
    assert record.placeholder_integrity is True
    assert record.prompt_tokens == 10
    assert record.completion_tokens == 20
    assert "title_quality_index" in record.quality_scores
    assert "description_quality_index" in record.quality_scores


def test_prompt_eval_summary_rates() -> None:
    records = [
        PromptEvalRecord(
            run_id="r",
            sku="sku-1",
            platform="google",
            variant="control",
            prompt_hash="a",
            schema_hash="b",
            prompt_tokens=1,
            completion_tokens=2,
            parse_mode="strict_json",
            missing_keys=[],
            title_len=80,
            desc_len=300,
            placeholder_integrity=True,
            policy_violations=[],
            quality_scores={
                "title_quality_index": {"overall": 80},
                "description_quality_index": {"overall": 78},
            },
        ),
        PromptEvalRecord(
            run_id="r",
            sku="sku-2",
            platform="google",
            variant="control",
            prompt_hash="a",
            schema_hash="b",
            prompt_tokens=1,
            completion_tokens=2,
            parse_mode="substring_fallback",
            missing_keys=["google_description"],
            title_len=75,
            desc_len=len("{FINISH_SENTENCE}"),
            placeholder_integrity=False,
            policy_violations=["policy check failed"],
            quality_scores={
                "title_quality_index": {"overall": 60},
                "description_quality_index": {"overall": 40},
            },
        ),
    ]
    rows = summarize_prompt_eval_records(records)
    assert len(rows) == 1
    row = rows[0]
    assert row["platform"] == "google"
    assert row["variant"] == "control"
    assert row["records"] == 2
    assert row["parse_fallback_rate"] == 0.5
    assert row["short_content_rate"] == 0.5
    assert row["empty_or_placeholder_rate"] == 0.5
    assert row["placeholder_failure_rate"] == 0.5
    assert row["policy_violation_rate"] == 0.5


def test_placeholder_only_detection_handles_punctuation_wrapped_placeholder() -> None:
    record = build_prompt_eval_record(
        run_id="run-2",
        sku="sku-punct",
        platform="google",
        variant="control",
        prompt_hash="p",
        schema_hash="s",
        usage={"prompt_tokens": 1, "completion_tokens": 1},
        parse_details={"parse_mode": "strict_json", "missing_keys": []},
        payload={
            "google_title": "{FINISH_NAME} Towel Bar",
            "google_description": "\"{FINISH_SENTENCE}.\"",
        },
        policy_violations=[],
    )
    row = summarize_prompt_eval_records([record])[0]
    assert row["empty_or_placeholder_rate"] == 1.0


@pytest.mark.asyncio
async def test_generate_per_platform_respects_selected_platforms(monkeypatch) -> None:
    from feedops.pipeline import generator as gen

    class StubProvider:
        async def generate(self, *, prompt, schema, system_prompt, reasoning_effort, max_completion_tokens):
            if "prompt-google" in prompt:
                self._last_usage = {"prompt_tokens": 11, "completion_tokens": 22}
                self._last_parse_details = {"parse_mode": "strict_json", "missing_keys": []}
                return {
                    "google_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar",
                    "google_short_title": "{FINISH_NAME} 24-Inch Towel Bar",
                    "google_description": "Solid brass towel bar copy. {FINISH_SENTENCE}",
                    "claims": [],
                }
            raise AssertionError(f"Unexpected prompt sent to provider: {prompt}")

        @property
        def last_usage(self):
            return getattr(self, "_last_usage", {})

        @property
        def last_parse_details(self):
            return getattr(self, "_last_parse_details", {})

        @property
        def last_retry_counts(self):
            return {"attempt_count": 1, "json_decode_retries": 0}

    monkeypatch.setattr(gen, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(gen, "filter_evidence_for_copy_context", lambda rows: rows)
    monkeypatch.setattr(gen, "get_category_guidance", lambda _category: "")
    monkeypatch.setattr(gen, "build_keyword_placement_plan", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gen, "format_keyword_placement_section", lambda _plan: "")
    monkeypatch.setattr(gen, "format_gold_standard_examples_bundle", lambda max_examples=2: "")
    monkeypatch.setattr(gen, "_build_finish_metadata_rows", lambda _sku: [])
    monkeypatch.setattr(gen, "build_google_prompt", lambda *_args, **_kwargs: "prompt-google")
    monkeypatch.setattr(gen, "build_bing_prompt", lambda *_args, **_kwargs: "prompt-bing")
    monkeypatch.setattr(gen, "build_shopify_prompt", lambda *_args, **_kwargs: "prompt-shopify")
    monkeypatch.setattr(gen, "build_finish_prompt", lambda *_args, **_kwargs: "prompt-finish")
    monkeypatch.setattr(gen, "get_platform_system_prompt", lambda platform: f"sys-{platform}")

    parent = ParentSKU(
        master_sku="1016",
        category="Towel Bars",
        current_title="24-Inch Wall Mount Towel Bar",
        current_description="Current description",
        variants=[],
    )

    result = await gen.generate_per_platform(
        parent_sku=parent,
        provider=StubProvider(),
        prompt_version="v2",
        selected_platforms=("google",),
    )
    expected_prompt_hash = hashlib.sha256(
        "sys-google\n\nprompt-google".encode("utf-8")
    ).hexdigest()
    assert result["google_title"].startswith("{FINISH_NAME}")
    assert result["prompt_hashes"]["google"] == expected_prompt_hash
    assert result["bing_title"] == ""
    assert result["shopify_title"] == ""
    assert result["retry_by_platform"]["google"]["attempt_count"] == 1


@pytest.mark.asyncio
async def test_generate_per_platform_enforces_request_cost_budget(monkeypatch) -> None:
    from feedops.pipeline import generator as gen

    class StubProvider:
        async def generate(self, *, prompt, schema, system_prompt, reasoning_effort, max_completion_tokens):
            assert prompt == "prompt-google"
            self._last_usage = {"prompt_tokens": 1200, "completion_tokens": 800}
            self._last_parse_details = {"parse_mode": "strict_json", "missing_keys": []}
            return {
                "google_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar",
                "google_short_title": "{FINISH_NAME} 24-Inch Towel Bar",
                "google_description": "Solid brass towel bar copy. {FINISH_SENTENCE}",
                "claims": [],
            }

        @property
        def last_usage(self):
            return getattr(self, "_last_usage", {})

        @property
        def last_parse_details(self):
            return getattr(self, "_last_parse_details", {})

        @property
        def last_retry_counts(self):
            return {"attempt_count": 1, "json_decode_retries": 0}

    monkeypatch.setenv("FEEDOPS_PROVIDER_REQUEST_COST_USD_CAP", "0.00001")
    monkeypatch.setattr(gen, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(gen, "filter_evidence_for_copy_context", lambda rows: rows)
    monkeypatch.setattr(gen, "get_category_guidance", lambda _category: "")
    monkeypatch.setattr(gen, "build_keyword_placement_plan", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gen, "format_keyword_placement_section", lambda _plan: "")
    monkeypatch.setattr(gen, "format_gold_standard_examples_bundle", lambda max_examples=2: "")
    monkeypatch.setattr(gen, "_build_finish_metadata_rows", lambda _sku: [])
    monkeypatch.setattr(gen, "build_google_prompt", lambda *_args, **_kwargs: "prompt-google")
    monkeypatch.setattr(gen, "build_bing_prompt", lambda *_args, **_kwargs: "prompt-bing")
    monkeypatch.setattr(gen, "build_shopify_prompt", lambda *_args, **_kwargs: "prompt-shopify")
    monkeypatch.setattr(gen, "build_finish_prompt", lambda *_args, **_kwargs: "prompt-finish")
    monkeypatch.setattr(gen, "get_platform_system_prompt", lambda platform: f"sys-{platform}")

    parent = ParentSKU(
        master_sku="1016",
        category="Towel Bars",
        current_title="24-Inch Wall Mount Towel Bar",
        current_description="Current description",
        variants=[],
    )

    with pytest.raises(gen.GenerationBudgetExceededError):
        await gen.generate_per_platform(
            parent_sku=parent,
            provider=StubProvider(),
            prompt_version="v2",
            selected_platforms=("google",),
        )


@pytest.mark.asyncio
async def test_generate_per_platform_budget_cap_honored_in_fallback_mode(monkeypatch) -> None:
    from feedops.pipeline import generator as gen

    class PrimaryProvider:
        def __init__(self) -> None:
            self._last_usage = {"prompt_tokens": 1300, "completion_tokens": 900}
            self._last_parse_details = {"parse_mode": "strict_json", "missing_keys": []}
            self._last_retry_counts = {"attempt_count": 1, "json_decode_retries": 0}

        @property
        def name(self) -> str:
            return "openai/test"

        @property
        def last_usage(self):
            return self._last_usage.copy()

        @property
        def last_parse_details(self):
            return self._last_parse_details.copy()

        @property
        def last_retry_counts(self):
            return self._last_retry_counts.copy()

        async def health_check(self) -> bool:
            return True

        async def generate(
            self,
            prompt,
            schema,
            image=None,
            system_prompt=None,
            reasoning_effort=None,
            max_completion_tokens=None,
        ):
            return {
                "google_title": "{FINISH_NAME} 24-Inch Wall Mount Towel Bar",
                "google_short_title": "{FINISH_NAME} 24-Inch Towel Bar",
                "google_description": "Solid brass towel bar copy. {FINISH_SENTENCE}",
                "claims": [],
            }

    class FallbackProviderStub:
        @property
        def name(self) -> str:
            return "gemini/test"

        async def health_check(self) -> bool:
            return True

        async def generate(
            self,
            prompt,
            schema,
            image=None,
            system_prompt=None,
            reasoning_effort=None,
            max_completion_tokens=None,
        ):
            raise AssertionError("fallback should not be called")

    monkeypatch.setenv("FEEDOPS_PROVIDER_REQUEST_COST_USD_CAP", "0.00001")
    monkeypatch.setattr(gen, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(gen, "filter_evidence_for_copy_context", lambda rows: rows)
    monkeypatch.setattr(gen, "get_category_guidance", lambda _category: "")
    monkeypatch.setattr(gen, "build_keyword_placement_plan", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(gen, "format_keyword_placement_section", lambda _plan: "")
    monkeypatch.setattr(gen, "format_gold_standard_examples_bundle", lambda max_examples=2: "")
    monkeypatch.setattr(gen, "_build_finish_metadata_rows", lambda _sku: [])
    monkeypatch.setattr(gen, "build_google_prompt", lambda *_args, **_kwargs: "prompt-google")
    monkeypatch.setattr(gen, "build_bing_prompt", lambda *_args, **_kwargs: "prompt-bing")
    monkeypatch.setattr(gen, "build_shopify_prompt", lambda *_args, **_kwargs: "prompt-shopify")
    monkeypatch.setattr(gen, "build_finish_prompt", lambda *_args, **_kwargs: "prompt-finish")
    monkeypatch.setattr(gen, "get_platform_system_prompt", lambda platform: f"sys-{platform}")

    parent = ParentSKU(
        master_sku="1016",
        category="Towel Bars",
        current_title="24-Inch Wall Mount Towel Bar",
        current_description="Current description",
        variants=[],
    )
    wrapper = FallbackProvider(primary=PrimaryProvider(), fallback=FallbackProviderStub())
    with pytest.raises(gen.GenerationBudgetExceededError):
        await gen.generate_per_platform(
            parent_sku=parent,
            provider=wrapper,
            prompt_version="v2",
            selected_platforms=("google",),
        )
