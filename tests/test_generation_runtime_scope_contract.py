from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import feedops.api.main as api_main
from feedops.api.multi_sku_detection import MultiSkuFamily
from tests.test_phase7_observability_reliability import (
    _CaptureSupabase,
    _patch_generation_deps,
    _sample_parent_sku,
)


async def _google_description_payload() -> dict:
    platform = "google"
    return {
        "google_description": (
            "Keep towels organized with this wall-mounted towel bar "
            "{FINISH_SENTENCE} Built from solid brass for daily use."
        ),
        "prompt_hashes": {platform: f"hash-{platform}"},
        "system_prompts": {platform: f"system-{platform}"},
        "user_prompts": {platform: f"user-{platform}"},
        "usage_by_platform": {
            platform: {"prompt_tokens": 120, "completion_tokens": 45}
        },
        "latency_by_platform": {platform: 125},
        "parse_by_platform": {
            platform: {"parse_mode": "strict_json", "missing_keys": []}
        },
        "retry_by_platform": {
            platform: {"attempt_count": 1, "json_decode_retries": 0}
        },
        "finish_sentences": {
            finish: f"{finish} complements this wall-mounted towel bar profile."
            for finish in api_main.get_finish_list()
        },
    }


async def _google_description_payload_with_finish_telemetry() -> dict:
    payload = await _google_description_payload()
    payload["usage_by_platform"]["finish"] = {
        "prompt_tokens": 40,
        "completion_tokens": 20,
    }
    payload["latency_by_platform"]["finish"] = 30
    payload["retry_by_platform"]["finish"] = {
        "attempt_count": 1,
        "json_decode_retries": 0,
    }
    return payload


async def _google_title_payload_with_fallback_finish_sentences() -> dict:
    return {
        "google_title": "{FINISH_NAME} Wall Mount Towel Bar - Skyline Collection - Allied Brass",
        "prompt_hashes": {"google": "hash-google"},
        "system_prompts": {"google": "system-google"},
        "user_prompts": {"google": "user-google"},
        "usage_by_platform": {"google": {"prompt_tokens": 100, "completion_tokens": 25}},
        "latency_by_platform": {"google": 90},
        "parse_by_platform": {
            "google": {"parse_mode": "strict_json", "missing_keys": []}
        },
        "retry_by_platform": {
            "google": {"attempt_count": 1, "json_decode_retries": 0}
        },
        # Legacy payloads always include this key even when no finish task ran.
        "finish_sentences": {
            finish: f"{finish} complements this wall-mounted towel bar profile."
            for finish in api_main.get_finish_list()
        },
    }


@pytest.mark.asyncio
async def test_process_batch_job_scopes_generation_to_requested_platforms(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-batch-scope")

    captured_calls: list[dict] = []

    async def _fake_generate_per_platform(**kwargs):
        captured_calls.append(kwargs)
        return await _google_description_payload()

    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)

    await api_main.process_batch_job(
        job_id="job-batch-scope",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    assert len(captured_calls) == 1
    assert captured_calls[0]["selected_platforms"] == ("google", "finish")


@pytest.mark.asyncio
async def test_process_batch_job_closes_provider(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-batch-close")

    async def _fake_generate_per_platform(**_kwargs):
        return await _google_description_payload()

    close_provider = AsyncMock()
    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)
    monkeypatch.setattr(api_main, "close_provider", close_provider)

    await api_main.process_batch_job(
        job_id="job-batch-close",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    close_provider.assert_awaited_once_with(provider)


@pytest.mark.asyncio
async def test_process_batch_job_description_scope_aggregates_finish_telemetry(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-batch-telemetry")

    async def _fake_generate_per_platform(**_kwargs):
        return await _google_description_payload_with_finish_telemetry()

    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)

    await api_main.process_batch_job(
        job_id="job-batch-telemetry",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    history_rows = [
        op
        for op in supabase.operations
        if op["table"] == "regeneration_history"
        and op["op"] == "insert"
        and op["payload"].get("content_type") == "description"
    ]
    assert len(history_rows) == 1
    assert history_rows[0]["payload"]["provider_attempt_count"] == 2
    assert history_rows[0]["payload"]["parse_retry_count"] == 0


@pytest.mark.asyncio
async def test_process_batch_job_title_only_skips_finish_sentence_writes(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-batch-title-only")

    async def _fake_generate_per_platform(**_kwargs):
        return await _google_title_payload_with_fallback_finish_sentences()

    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)

    await api_main.process_batch_job(
        job_id="job-batch-title-only",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": True, "descriptions": False, "platforms": ["google"]},
    )

    finish_rows = [
        op for op in supabase.operations if op["table"] == "variant_finish_sentences"
    ]
    assert finish_rows == []


@pytest.mark.asyncio
async def test_process_hybrid_batch_job_uses_adaptation_for_family_variants(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-hybrid-scope")

    def _load_parent(master_sku: str):
        sku = _sample_parent_sku()
        sku.master_sku = master_sku
        return sku

    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", _load_parent)

    generate_calls: list[str] = []

    async def _fake_generate_per_platform(**kwargs):
        parent_sku = kwargs["parent_sku"]
        generate_calls.append(parent_sku.master_sku)
        return await _google_description_payload()

    adapt_variant = AsyncMock(return_value={"success": True, "content": "adapted"})
    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)
    monkeypatch.setattr(api_main, "adapt_variant_content", adapt_variant)

    families = [
        MultiSkuFamily(
            product_id="family-1033",
            master_skus=["1033/18", "1033/24"],
            base_sku="1033/18",
            variant_skus=["1033/24"],
        )
    ]

    await api_main.process_hybrid_batch_job(
        job_id="job-hybrid-scope",
        families=families,
        single_skus=[],
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    assert generate_calls == ["1033/18"]
    adapt_variant.assert_awaited_once()
    assert adapt_variant.await_args.kwargs["base_sku"] == "1033/18"
    assert adapt_variant.await_args.kwargs["variant_sku"] == "1033/24"
    assert adapt_variant.await_args.kwargs["platform"] == "google"
    assert adapt_variant.await_args.kwargs["content_type"] == "description"


@pytest.mark.asyncio
async def test_process_hybrid_batch_job_description_scope_aggregates_finish_telemetry(
    monkeypatch,
):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-hybrid-telemetry")

    def _load_parent(master_sku: str):
        sku = _sample_parent_sku()
        sku.master_sku = master_sku
        return sku

    async def _fake_generate_per_platform(**_kwargs):
        return await _google_description_payload_with_finish_telemetry()

    monkeypatch.setattr(api_main, "load_parent_sku_from_supabase", _load_parent)
    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)
    monkeypatch.setattr(
        api_main,
        "adapt_variant_content",
        AsyncMock(return_value={"success": True, "content": "adapted"}),
    )

    families = [
        MultiSkuFamily(
            product_id="family-1033",
            master_skus=["1033/18", "1033/24"],
            base_sku="1033/18",
            variant_skus=["1033/24"],
        )
    ]

    await api_main.process_hybrid_batch_job(
        job_id="job-hybrid-telemetry",
        families=families,
        single_skus=[],
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    history_rows = [
        op
        for op in supabase.operations
        if op["table"] == "regeneration_history"
        and op["op"] == "insert"
        and op["payload"].get("master_sku") == "1033/18"
        and op["payload"].get("content_type") == "description"
    ]
    assert len(history_rows) == 1
    assert history_rows[0]["payload"]["provider_attempt_count"] == 2
    assert history_rows[0]["payload"]["parse_retry_count"] == 0


@pytest.mark.asyncio
async def test_process_hybrid_batch_job_closes_provider(monkeypatch):
    supabase = _CaptureSupabase()
    provider = object()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_main, "get_request_id", lambda: "req-hybrid-close")

    async def _fake_generate_per_platform(**_kwargs):
        return await _google_description_payload()

    close_provider = AsyncMock()
    monkeypatch.setattr(api_main, "generate_per_platform", _fake_generate_per_platform)
    monkeypatch.setattr(api_main, "close_provider", close_provider)

    families = [
        MultiSkuFamily(
            product_id="family-1033",
            master_skus=["1033/18", "1033/24"],
            base_sku="1033/18",
            variant_skus=["1033/24"],
        )
    ]

    await api_main.process_hybrid_batch_job(
        job_id="job-hybrid-close",
        families=families,
        single_skus=[],
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    close_provider.assert_awaited_once_with(provider)
