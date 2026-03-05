from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

import feedops.api.routes as api_routes
import feedops.api.schemas as api_schemas
import feedops.api.generation as api_generation
import feedops.api.job_runner as api_job_runner
import feedops.api.job_management as api_job_management
from feedops.api.hybrid_generation import build_variant_adaptation_prompt
from feedops.api.multi_sku_detection import MultiSkuFamily
from feedops.api.prompt_loader import get_finish_list
from feedops.pipeline.finish_sentence_placeholder import inject_finish_sentence_placeholder
from feedops.models import ParentSKU, Variant
from feedops.providers.base import LLMError
from feedops.providers.openai_provider import OpenAIProvider
from feedops.providers.reliability import circuit_breakers


@pytest.fixture(autouse=True)
def _reset_runtime_state(monkeypatch):
    from feedops.observability.metrics import metrics_registry

    metrics_registry.reset()
    circuit_breakers.reset()
    monkeypatch.delenv("FEEDOPS_DISABLE_GENERATION", raising=False)
    monkeypatch.delenv("FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN", raising=False)
    monkeypatch.delenv("FEEDOPS_PROVIDER_CIRCUIT_FAILURE_THRESHOLD", raising=False)
    monkeypatch.delenv("FEEDOPS_PROVIDER_CIRCUIT_COOLDOWN_SECONDS", raising=False)
    yield
    metrics_registry.reset()
    circuit_breakers.reset()


def _sample_parent_sku() -> ParentSKU:
    variant = Variant(
        option_sku="1031/18-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_4542872518788_32118222192772",
        position=1,
    )
    return ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="This stylish towel bar...",
        material="Brass",
        mounting_type="Wall mount",
        weight_capacity=10.0,
        variants=[variant],
    )


class _FakeTable:
    def __init__(self):
        self._is_select = False

    def insert(self, *_args, **_kwargs):
        self._is_select = False
        return self

    def update(self, *_args, **_kwargs):
        self._is_select = False
        return self

    def upsert(self, *_args, **_kwargs):
        self._is_select = False
        return self

    def select(self, *_args, **_kwargs):
        self._is_select = True
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def execute(self):
        if self._is_select:
            return SimpleNamespace(data=None)
        return SimpleNamespace(data=[{"id": "job-1"}])


@dataclass
class _FakeSupabase:
    def table(self, _name: str) -> _FakeTable:
        return _FakeTable()


class _FakeProvider:
    def __init__(self, responses: list[dict]):
        self._responses = responses
        self.calls = 0
        self.name = "fake/provider"

    async def generate(self, *args, **kwargs) -> dict:
        schema = kwargs.get("schema") or (args[1] if len(args) > 1 else {})
        required = set((schema or {}).get("required", []))

        if self.calls < len(self._responses):
            result = self._responses[self.calls]
        else:
            result = {}
        self.calls += 1

        # Preserve explicit finish payloads from tests.
        if isinstance(result, dict) and "finish_sentences" in result:
            return result

        # Backward-compat for legacy test fixtures that return {"content": "..."}.
        if isinstance(result, dict) and "content" in result and len(required) == 1:
            required_key = next(iter(required))
            return {required_key: result["content"]}

        if isinstance(result, dict) and required and required.issubset(result.keys()):
            return result

        payload: dict[str, object] = {}
        for key in required:
            if key == "finish_sentences":
                payload[key] = {
                    finish: f"{finish} complements this wall-mounted towel bar profile."
                    for finish in get_finish_list()
                }
            elif key in {"google_description", "bing_description"}:
                payload[key] = (
                    "Keep towels organized with this wall-mounted towel bar "
                    "{FINISH_SENTENCE} Built from solid brass for daily use."
                )
            elif key == "shopify_description":
                payload[key] = (
                    "Keep towels organized with this wall-mounted towel bar built from "
                    "solid brass for daily use."
                )
            elif key == "shopify_meta_description":
                payload[key] = "Solid brass wall-mounted towel bar for everyday bathroom storage."
            elif key == "google_short_title":
                payload[key] = "18 Inch Brass Towel Bar"
            elif key.endswith("_title"):
                payload[key] = "Skyline 18 Inch Wall-Mounted Brass Towel Bar"
        return payload


class _RecordingProvider:
    def __init__(self):
        self.calls: list[dict] = []
        self.name = "fake/parity-provider"

    async def generate(self, prompt, schema, system_prompt) -> dict:
        self.calls.append(
            {"prompt": prompt, "schema": schema, "system_prompt": system_prompt}
        )
        required = set((schema or {}).get("required", []))
        payload: dict[str, object] = {}
        for key in required:
            if key == "finish_sentences":
                payload[key] = {
                    finish: f"{finish} complements this wall-mounted towel bar profile."
                    for finish in get_finish_list()
                }
            elif key in {"google_description", "bing_description"}:
                payload[key] = (
                    "Keep towels organized with this wall-mounted towel bar "
                    "{FINISH_SENTENCE} Built from solid brass for daily use."
                )
            elif key == "shopify_description":
                payload[key] = (
                    "Keep towels organized with this wall-mounted towel bar built from "
                    "solid brass for daily use."
                )
            elif key == "shopify_meta_description":
                payload[key] = "Solid brass wall-mounted towel bar for everyday bathroom storage."
            elif key == "google_short_title":
                payload[key] = "18 Inch Brass Towel Bar"
            elif key.endswith("_title"):
                payload[key] = "Skyline 18 Inch Wall-Mounted Brass Towel Bar"
        return payload


class _CaptureTable:
    def __init__(self, db: "_CaptureSupabase", name: str):
        self._db = db
        self._name = name
        self._filters: dict[str, object] = {}
        self._select_columns: tuple[str, ...] = ()

    def insert(self, payload, **_kwargs):
        if self._name == "generated_content":
            self._db.store_generated_content(payload)
        self._db.operations.append(
            {"op": "insert", "table": self._name, "payload": payload}
        )
        return self

    def upsert(self, payload, on_conflict=None, **_kwargs):
        if self._name == "generated_content":
            self._db.store_generated_content(payload)
        self._db.operations.append(
            {
                "op": "upsert",
                "table": self._name,
                "payload": payload,
                "on_conflict": on_conflict,
            }
        )
        return self

    def update(self, payload, **_kwargs):
        if self._name == "generated_content":
            self._db.store_generated_content(payload)
        self._db.operations.append(
            {"op": "update", "table": self._name, "payload": payload}
        )
        return self

    def select(self, *columns, **_kwargs):
        self._select_columns = columns
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def maybe_single(self):
        return self

    def single(self):
        return self

    def execute(self):
        if self._name == "generated_content" and self._select_columns:
            row = self._db.find_generated_content(self._filters)
            if row:
                return SimpleNamespace(data=row)
            return SimpleNamespace(data=None)
        return SimpleNamespace(data=None)


@dataclass
class _CaptureSupabase:
    operations: list[dict]

    def __init__(self):
        self.operations = []
        self._generated_content: dict[tuple[str, str, str], dict] = {}
        self._id_counter = 0

    def table(self, name: str) -> _CaptureTable:
        return _CaptureTable(self, name)

    def store_generated_content(self, payload: dict):
        master_sku = payload.get("master_sku")
        platform = payload.get("platform")
        content_type = payload.get("content_type")
        if not master_sku or not platform or not content_type:
            return
        key = (master_sku, platform, content_type)
        existing = self._generated_content.get(key, {})
        if "id" not in existing:
            self._id_counter += 1
            existing["id"] = f"generated-{self._id_counter}"
        existing.update(payload)
        self._generated_content[key] = existing

    def find_generated_content(self, filters: dict[str, object]) -> dict | None:
        key = (
            filters.get("master_sku"),
            filters.get("platform"),
            filters.get("content_type"),
        )
        row = self._generated_content.get(key)
        if not row:
            return None
        return dict(row)


class _BatchJobTable:
    def __init__(self, db: "_BatchJobSupabase", name: str):
        self._db = db
        self._name = name
        self._payload = None

    def insert(self, payload, **_kwargs):
        self._payload = payload
        if self._name == "batch_generation_jobs":
            self._db.job_payloads.append(payload)
        elif self._name == "batch_generation_job_skus":
            self._db.sku_payloads.append(payload)
        return self

    def execute(self):
        if self._name == "batch_generation_jobs":
            return SimpleNamespace(data=[{"id": "job-xyz"}])
        return SimpleNamespace(data=[])


@dataclass
class _BatchJobSupabase:
    job_payloads: list[dict]
    sku_payloads: list[list[dict]]

    def __init__(self):
        self.job_payloads = []
        self.sku_payloads = []

    def table(self, name: str) -> _BatchJobTable:
        return _BatchJobTable(self, name)


def _patch_generation_deps(monkeypatch, provider, supabase):
    # Patch at routes module (where optimize_single_sku / batch_optimize / regenerate_content live)
    monkeypatch.setattr(api_routes, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_routes, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(api_routes, "format_evidence_markdown", lambda _evidence: "table")
    monkeypatch.setattr(api_routes, "get_provider", lambda: provider)
    monkeypatch.setattr(api_routes, "get_client", lambda: supabase)
    monkeypatch.setattr(api_routes, "ensure_generation_enabled", lambda **_kwargs: None)
    monkeypatch.setattr(api_routes, "resolve_canonical_master_sku", lambda _supabase, sku: sku)
    monkeypatch.setattr(api_routes, "resolve_canonical_master_skus", lambda _supabase, skus: skus)
    # Also patch at generation module (where _execute_regeneration_request lives after extraction)
    monkeypatch.setattr(api_generation, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_generation, "get_provider", lambda: provider)
    monkeypatch.setattr(api_generation, "get_client", lambda: supabase)
    monkeypatch.setattr(api_generation, "resolve_canonical_master_sku", lambda _supabase, sku: sku)
    # Also patch at job_runner module (where process_batch/hybrid_job logic lives after Plan 03-01)
    monkeypatch.setattr(api_job_runner, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_job_runner, "get_provider", lambda: provider)
    monkeypatch.setattr(api_job_runner, "get_client", lambda: supabase)
    monkeypatch.setattr(api_job_runner, "resolve_canonical_master_sku", lambda _supabase, sku: sku)
    monkeypatch.setattr(api_job_runner, "ensure_generation_enabled", lambda **_kwargs: None)


def test_structured_log_event_includes_request_id(caplog):
    from feedops.observability import log_event, request_context

    logger = logging.getLogger("phase7.test")
    with caplog.at_level(logging.INFO):
        with request_context("req-phase7-123"):
            log_event(logger, logging.INFO, "generation.started", sku="ABC-123")

    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "generation.started"
    assert payload["request_id"] == "req-phase7-123"
    assert payload["sku"] == "ABC-123"


def test_metrics_registry_tracks_latency_retry_and_errors():
    from feedops.observability.metrics import metrics_registry

    metrics_registry.reset()
    metrics_registry.increment("provider_retry_total", provider="openai")
    metrics_registry.increment("provider_error_total", provider="openai")
    with metrics_registry.timer("generation_latency_seconds", endpoint="regenerate"):
        pass

    snapshot = metrics_registry.snapshot()
    assert snapshot["counters"][("provider_retry_total", (("provider", "openai"),))] == 1
    assert snapshot["counters"][("provider_error_total", (("provider", "openai"),))] == 1
    assert (
        len(snapshot["timings"][("generation_latency_seconds", (("endpoint", "regenerate"),))])
        == 1
    )


@pytest.mark.asyncio
async def test_openai_provider_applies_backoff_on_retryable_error():
    provider = OpenAIProvider(api_key="test-key", max_retries=2)

    valid_response = MagicMock()
    valid_response.choices = [MagicMock()]
    valid_response.choices[0].message.content = '{"title": "Recovered"}'
    valid_response.usage.prompt_tokens = 100
    valid_response.usage.completion_tokens = 50

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        with patch(
            "feedops.providers.openai_provider.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            mock_create.side_effect = [Exception("429 rate limit"), valid_response]

            result = await provider.generate("Test prompt", {"type": "object"})
            assert result["title"] == "Recovered"
            mock_sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_provider_circuit_breaker_blocks_after_threshold(monkeypatch):
    monkeypatch.setenv("FEEDOPS_PROVIDER_CIRCUIT_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("FEEDOPS_PROVIDER_CIRCUIT_COOLDOWN_SECONDS", "60")

    provider = OpenAIProvider(api_key="test-key", max_retries=1)

    with patch.object(
        provider.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = Exception("429 rate limit")

        with pytest.raises(LLMError):
            await provider.generate("Test prompt", {"type": "object"})

        with pytest.raises(LLMError, match="Circuit breaker open"):
            await provider.generate("Test prompt", {"type": "object"})

        assert mock_create.call_count == 1


@pytest.mark.asyncio
async def test_optimize_single_sku_respects_generation_kill_switch(monkeypatch):
    monkeypatch.setenv("FEEDOPS_DISABLE_GENERATION", "1")

    def _unexpected_load(*_args, **_kwargs):
        raise AssertionError("load_parent_sku_from_supabase should not be called")

    monkeypatch.setattr(api_routes, "load_parent_sku_from_supabase", _unexpected_load)

    request = api_schemas.OptimizeRequest(master_sku="1031/18", num_candidates=1, dry_run=True)
    with pytest.raises(HTTPException) as exc_info:
        await api_routes.optimize_single_sku(request)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_regenerate_description_uses_fallback_finish_sentences_when_killed(
    monkeypatch,
):
    monkeypatch.setenv("FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN", "1")

    fake_provider = _FakeProvider(
        [
            {
                "content": (
                    "Antique Brass keeps towels organized in this wall-mounted towel bar. "
                    "Choose from 28 designer finishes to coordinate your bath."
                )
            }
        ]
    )

    monkeypatch.setattr(api_routes, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_routes, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(api_routes, "format_evidence_markdown", lambda _evidence: "table")
    monkeypatch.setattr(api_routes, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_routes, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_routes, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(api_routes, "get_system_prompt_hash", lambda: "hash123")
    monkeypatch.setattr(api_routes, "get_category_guidance", lambda _category: "")
    # Also patch at generation module (where _execute_regeneration_request lives after extraction)
    monkeypatch.setattr(api_generation, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_generation, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_generation, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_generation, "resolve_canonical_master_sku", lambda _supabase, sku: sku)

    request = api_schemas.RegenerateRequest(
        master_sku="1031/18",
        content_type="description",
        platform="google",
        feedback=None,
        finish_code="ABR",
    )
    response = await api_routes.regenerate_content(request)

    assert response.success is True
    assert response.finish_sentences is not None
    assert len(response.finish_sentences) == len(get_finish_list())
    assert "{FINISH_SENTENCE}" in response.content
    assert response.content.count("{FINISH_SENTENCE}") == 1
    assert "Antique Brass" not in response.content
    assert "choose from 28 designer finishes" not in response.content.lower()
    assert fake_provider.calls == 1


@pytest.mark.asyncio
async def test_regenerate_description_injects_finish_sentence_placeholder_when_finish_sentences_present(monkeypatch):
    fake_provider = _FakeProvider(
        [
            {"content": "Keep towels organized with this wall-mounted towel bar."},
            {"finish_sentences": {finish: f"{finish} complements this towel bar design." for finish in get_finish_list()}},
        ]
    )

    monkeypatch.setattr(api_routes, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_routes, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(api_routes, "format_evidence_markdown", lambda _evidence: "table")
    monkeypatch.setattr(api_routes, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_routes, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_routes, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(api_routes, "get_system_prompt_hash", lambda: "hash123")
    monkeypatch.setattr(api_routes, "get_category_guidance", lambda _category: "")
    # Also patch at generation module (where _execute_regeneration_request lives after extraction)
    monkeypatch.setattr(api_generation, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_generation, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_generation, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_generation, "resolve_canonical_master_sku", lambda _supabase, sku: sku)

    request = api_schemas.RegenerateRequest(
        master_sku="1031/18",
        content_type="description",
        platform="google",
        feedback=None,
        finish_code="ABR",
    )
    response = await api_routes.regenerate_content(request)

    assert response.success is True
    assert response.finish_sentences is not None
    assert "{FINISH_SENTENCE}" in response.content
    assert response.content.count("{FINISH_SENTENCE}") == 1
    assert fake_provider.calls == 2


@pytest.mark.asyncio
async def test_regenerate_description_falls_back_when_finish_sentences_incomplete(
    monkeypatch,
):
    fake_provider = _FakeProvider(
        [
            {
                "content": (
                    "Polished Nickel keeps towels organized with a wall-mounted profile."
                )
            },
            {"finish_sentences": {"Antique Brass": "Antique Brass warms the space."}},
        ]
    )

    monkeypatch.setattr(api_routes, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_routes, "build_evidence_table", lambda _sku: [])
    monkeypatch.setattr(api_routes, "format_evidence_markdown", lambda _evidence: "table")
    monkeypatch.setattr(api_routes, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_routes, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_routes, "get_system_prompt", lambda: "system")
    monkeypatch.setattr(api_routes, "get_system_prompt_hash", lambda: "hash123")
    monkeypatch.setattr(api_routes, "get_category_guidance", lambda _category: "")
    # Also patch at generation module (where _execute_regeneration_request lives after extraction)
    monkeypatch.setattr(api_generation, "load_parent_sku_from_supabase", lambda _sku: _sample_parent_sku())
    monkeypatch.setattr(api_generation, "get_provider", lambda: fake_provider)
    monkeypatch.setattr(api_generation, "get_client", lambda: _FakeSupabase())
    monkeypatch.setattr(api_generation, "resolve_canonical_master_sku", lambda _supabase, sku: sku)

    request = api_schemas.RegenerateRequest(
        master_sku="1031/18",
        content_type="description",
        platform="google",
        feedback=None,
        finish_code="ABR",
    )
    response = await api_routes.regenerate_content(request)

    assert response.success is True
    assert response.finish_sentences is not None
    # Regeneration path passes through finish sentences from executor;
    # incomplete coverage is returned as-is (fallback only in optimization path)
    assert len(response.finish_sentences) >= 1
    assert "{FINISH_SENTENCE}" in response.content
    assert response.content.count("{FINISH_SENTENCE}") == 1
    assert "Polished Nickel" not in response.content
    assert fake_provider.calls == 2


def test_inject_finish_sentence_placeholder_is_idempotent():
    base = "Solid brass construction. {FINISH_SENTENCE} Concealed mounting keeps installation clean."
    assert inject_finish_sentence_placeholder(base) == base


def test_inject_finish_sentence_placeholder_collapses_duplicates():
    base = (
        "Solid brass construction. {FINISH_SENTENCE} Concealed mounting keeps installation clean. "
        "{FINISH_SENTENCE}"
    )
    normalized = inject_finish_sentence_placeholder(base)
    assert normalized.count("{FINISH_SENTENCE}") == 1


@pytest.mark.asyncio
async def test_optimize_single_sku_google_bing_description_parity_with_regenerate(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)

    response = await api_routes.optimize_single_sku(
        api_schemas.OptimizeRequest(master_sku="1031/18", num_candidates=1, dry_run=False)
    )

    assert response.success is True

    desc_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "upsert"
        and op["table"] == "generated_content"
        and op["payload"].get("content_type") == "description"
        and op["payload"].get("platform") in {"google", "bing"}
    ]
    assert len(desc_rows) == 2
    for row in desc_rows:
        candidate = row["candidate_content"]
        assert "{FINISH_SENTENCE}" in candidate
        assert candidate.count("{FINISH_SENTENCE}") == 1
        assert "available in 28 designer finishes" not in candidate.lower()
        assert isinstance(row["generation_prompt_hash"], str)
        assert row["generation_prompt_hash"]
        assert row["generation_model"] == provider.name

    finish_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "upsert" and op["table"] == "variant_finish_sentences"
    ]
    assert len(finish_rows) == 2
    for row in finish_rows:
        assert row["platform"] in {"google", "bing"}
        assert len(row["finish_sentences"]) == len(get_finish_list())


@pytest.mark.asyncio
async def test_process_hybrid_batch_job_full_generation_matches_regenerate_finish_rules(
    monkeypatch,
):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)

    await api_job_runner.JobRunner(mode="hybrid")._run_hybrid(
        job_id="job-123",
        families=[],
        single_skus=["1031/18"],
        options={"titles": False, "descriptions": True, "platforms": ["google", "bing"]},
    )

    desc_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "upsert"
        and op["table"] == "generated_content"
        and op["payload"].get("content_type") == "description"
        and op["payload"].get("platform") in {"google", "bing"}
    ]
    assert len(desc_rows) == 2
    for row in desc_rows:
        candidate = row["candidate_content"]
        assert "{FINISH_SENTENCE}" in candidate
        assert candidate.count("{FINISH_SENTENCE}") == 1
        assert "available in 28 designer finishes" not in candidate.lower()
        assert isinstance(row["generation_prompt_hash"], str)
        assert row["generation_prompt_hash"]
        assert row["generation_model"] == provider.name

    finish_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "upsert" and op["table"] == "variant_finish_sentences"
    ]
    assert len(finish_rows) == 2
    for row in finish_rows:
        assert row["platform"] in {"google", "bing"}
        assert len(row["finish_sentences"]) == len(get_finish_list())


def test_build_variant_adaptation_prompt_shopify_description_does_not_fallback_to_title_prompt():
    prompt, requires_json = build_variant_adaptation_prompt(
        content_type="description",
        platform="shopify",
        base_sku="SB-16",
        variant_sku="SB-18",
        base_content="Base Shopify description body",
        base_spec="16 inch",
        variant_spec="18 inch",
        include_finish_sentences=True,
    )

    assert requires_json is False
    assert "adapting product content for a variant specification" in prompt.lower()
    assert "base content" in prompt.lower()
    assert "base title" not in prompt.lower()
    assert "Respond with ONLY the adapted description text." in prompt


@pytest.mark.asyncio
async def test_optimize_single_sku_persists_linked_history_for_all_platforms(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)

    response = await api_routes.optimize_single_sku(
        api_schemas.OptimizeRequest(master_sku="1031/18", num_candidates=1, dry_run=False)
    )

    assert response.success is True
    history_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "insert" and op["table"] == "regeneration_history"
    ]
    # 7 rows: title+description for google/bing/shopify (6) + finish_sentences (1)
    assert len(history_rows) == 7

    content_rows = [r for r in history_rows if r["content_type"] != "finish_sentences"]
    finish_rows = [r for r in history_rows if r["content_type"] == "finish_sentences"]
    assert len(content_rows) == 6
    assert len(finish_rows) == 1

    for row in content_rows:
        assert row["mode"] == "full_generation_v2"
        assert row["generated_content_id"] is not None
        assert row["model_version"] == provider.name
        assert isinstance(row["prompt_hash"], str)
        assert row["prompt_hash"]


@pytest.mark.asyncio
async def test_process_batch_job_persists_linked_history_for_all_platforms(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)

    await api_job_runner.JobRunner(mode="batch")._run_batch(
        job_id="job-123",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
    )

    history_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "insert" and op["table"] == "regeneration_history"
    ]
    # 7 rows: title+description for google/bing/shopify (6) + finish_sentences (1)
    assert len(history_rows) == 7
    platforms = {row["platform"] for row in history_rows}
    assert platforms == {"google", "bing", "shopify", "finish"}
    content_rows = [r for r in history_rows if r["content_type"] != "finish_sentences"]
    assert len(content_rows) == 6
    for row in content_rows:
        assert row["generated_content_id"] is not None
        assert row["mode"] == "full_generation_v2"


@pytest.mark.asyncio
async def test_process_batch_job_persists_platform_telemetry_once_per_platform(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(api_job_management, "get_request_id", lambda: "req-batch-telemetry-once")

    async def _fake_generate_per_platform(**_kwargs):
        return {
            "google_title": "Google title",
            "google_description": "Google description {FINISH_SENTENCE}",
            "prompt_hashes": {"google": "hash-google"},
            "system_prompts": {"google": "sys-google"},
            "user_prompts": {"google": "user-google"},
            "usage_by_platform": {"google": {"prompt_tokens": 120, "completion_tokens": 45}},
            "latency_by_platform": {"google": 125},
            "parse_by_platform": {"google": {"parse_mode": "strict_json", "missing_keys": []}},
            "retry_by_platform": {"google": {"attempt_count": 2, "json_decode_retries": 1}},
        }

    monkeypatch.setattr(api_job_runner, "generate_per_platform", _fake_generate_per_platform)
    summary_events: list[dict] = []
    monkeypatch.setattr(api_job_runner, "_emit_generation_summary", lambda **kwargs: summary_events.append(kwargs))

    await api_job_runner.JobRunner(mode="batch")._run_batch(
        job_id="job-telemetry-once",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": True, "descriptions": True, "platforms": ["google"]},
    )

    history_rows = [
        op["payload"]
        for op in supabase.operations
        if op["op"] == "insert" and op["table"] == "regeneration_history"
    ]
    assert len(history_rows) == 2
    assert all(row.get("tokens_used") is not None for row in history_rows)
    assert all(row.get("cost_usd") is not None for row in history_rows)
    assert all(row.get("latency_ms") is not None for row in history_rows)
    assert sum(1 for row in history_rows if (row.get("tokens_used") or 0) > 0) == 1
    assert sum(1 for row in history_rows if (row.get("cost_usd") or 0) > 0) == 1
    assert sum(1 for row in history_rows if (row.get("latency_ms") or 0) > 0) == 1

    platform_summaries = [
        event
        for event in summary_events
        if event.get("endpoint") == "process_batch_job"
        and event.get("platform") == "google"
        and event.get("result_state") == "completed"
    ]
    assert len(platform_summaries) == 2
    assert all(event.get("tokens_used") is not None for event in platform_summaries)
    assert all(event.get("cost_usd") is not None for event in platform_summaries)
    assert all(event.get("latency_ms") is not None for event in platform_summaries)
    assert sum(1 for event in platform_summaries if (event.get("tokens_used") or 0) > 0) == 1
    assert sum(1 for event in platform_summaries if (event.get("cost_usd") or 0) > 0) == 1
    assert sum(1 for event in platform_summaries if (event.get("latency_ms") or 0) > 0) == 1


def test_batch_optimize_request_exposes_generation_options_field():
    assert "options" in api_schemas.BatchOptimizeRequest.model_fields


@pytest.mark.asyncio
async def test_batch_optimize_passes_generation_options_to_background_job(monkeypatch):
    supabase = _BatchJobSupabase()
    captured: dict[str, object] = {}

    def _capture_run_async(async_func, request_id=None, **kwargs):
        captured["func_name"] = getattr(async_func, "__name__", "")
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(api_routes, "get_client", lambda: supabase)
    monkeypatch.setattr(api_routes, "resolve_canonical_master_skus", lambda _supabase, skus: skus)
    monkeypatch.setattr(api_routes, "run_async_in_thread", _capture_run_async)
    monkeypatch.setattr(api_routes, "get_request_id", lambda: "req-123")

    request = api_schemas.BatchOptimizeRequest.model_validate(
        {
            "skus": ["1031/18", "920D-6"],
            "num_candidates": 1,
            "dry_run": False,
            "options": {
                "titles": False,
                "descriptions": True,
                "platforms": ["google"],
            },
        }
    )

    response = await api_routes.batch_optimize(request)

    assert response.success is True
    assert captured["func_name"] == "run"  # JobRunner(mode="batch").run after Plan 03-01 extraction
    assert captured["kwargs"]["options"] == {
        "titles": False,
        "descriptions": True,
        "platforms": ["google"],
    }
    assert supabase.job_payloads
    assert supabase.job_payloads[0]["options"]["titles"] is False
    assert supabase.job_payloads[0]["options"]["descriptions"] is True
    assert supabase.job_payloads[0]["options"]["platforms"] == ["google"]


@pytest.mark.asyncio
async def test_process_batch_job_respects_options_for_platform_and_content_type(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)

    await api_job_runner.JobRunner(mode="batch")._run_batch(
        job_id="job-123",
        skus=["1031/18"],
        num_candidates=1,
        dry_run=False,
        options={"titles": False, "descriptions": True, "platforms": ["google"]},
    )

    generated_rows = [
        op["payload"]
        for op in supabase.operations
        if op["table"] == "generated_content"
        and op["op"] == "upsert"
    ]
    assert len(generated_rows) == 1
    assert generated_rows[0]["platform"] == "google"
    assert generated_rows[0]["content_type"] == "description"

    history_rows = [
        op["payload"]
        for op in supabase.operations
        if op["table"] == "regeneration_history"
        and op["op"] == "insert"
    ]
    assert len(history_rows) == 2
    content_types = {row["content_type"] for row in history_rows}
    assert content_types == {"description", "finish_sentences"}
    desc_row = [r for r in history_rows if r["content_type"] == "description"][0]
    assert desc_row["platform"] == "google"


@pytest.mark.asyncio
async def test_process_batch_job_never_writes_partial_status(monkeypatch):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)
    sample = _sample_parent_sku()
    monkeypatch.setattr(
        api_job_runner,
        "load_parent_sku_from_supabase",
        lambda sku: sample if sku == "1031/18" else None,
    )

    await api_job_runner.JobRunner(mode="batch")._run_batch(
        job_id="job-123",
        skus=["1031/18", "missing-sku"],
        num_candidates=1,
        dry_run=False,
    )

    job_updates = [
        op["payload"]
        for op in supabase.operations
        if op["table"] == "batch_generation_jobs" and op["op"] == "update"
    ]

    assert job_updates
    assert all(update.get("status") != "partial" for update in job_updates)
    final_status = [update for update in job_updates if "status" in update][-1]
    # Partial success (1 completed, 1 failed) is "completed" — only all-failures is "failed"
    assert final_status["status"] == "completed"
    assert final_status["failed_skus"] == 1
    assert final_status["completed_skus"] == 1


@pytest.mark.asyncio
async def test_process_hybrid_batch_job_tracks_requested_and_expanded_counters(
    monkeypatch,
):
    provider = _RecordingProvider()
    supabase = _CaptureSupabase()
    _patch_generation_deps(monkeypatch, provider, supabase)
    monkeypatch.setattr(
        api_job_runner,
        "adapt_variant_content",
        AsyncMock(return_value={"success": True, "content": "adapted"}),
    )

    families = [
        MultiSkuFamily(
            product_id="family-1",
            master_skus=["A-16", "A-18", "A-24"],
            base_sku="A-16",
            variant_skus=["A-18", "A-24"],
        )
    ]

    await api_job_runner.JobRunner(mode="hybrid")._run_hybrid(
        job_id="job-123",
        families=families,
        single_skus=["SB-16"],
        requested_skus=["SB-16", "A-18"],
        options={
            "titles": True,
            "descriptions": True,
            "platforms": ["google", "bing", "shopify"],
        },
    )

    job_updates = [
        op["payload"]
        for op in supabase.operations
        if op["table"] == "batch_generation_jobs" and op["op"] == "update"
    ]
    assert job_updates
    assert all(update.get("status") != "partial" for update in job_updates)

    final_status = [update for update in job_updates if "status" in update][-1]
    assert final_status["status"] == "completed"
    assert final_status["completed_skus"] == 2
    assert final_status["failed_skus"] == 0
    assert final_status["completed_skus"] + final_status["failed_skus"] == 2

    options = final_status["options"]
    assert options["expanded_total_skus"] == 2
    assert options["expanded_completed_skus"] == 2
    assert options["expanded_failed_skus"] == 0
