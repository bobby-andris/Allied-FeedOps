from __future__ import annotations

import pytest

from feedops.generation.executor import execute_generation_bundle
from feedops.models import ParentSKU, Variant
from feedops.pipeline.query_intent_brief import (
    QueryIntentBrief,
    QueryIntentDiagnostics,
    QueryIntentSection,
)


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.last_usage = {
            "prompt_tokens": 120,
            "completion_tokens": 40,
            "cached_tokens": 0,
        }
        self.last_parse_details = {"parse_mode": "strict_json", "missing_keys": []}
        self.last_retry_counts = {"attempt_count": 1, "json_decode_retries": 0}

    async def generate(self, **kwargs) -> dict[str, object]:
        self.calls.append(kwargs)
        schema = kwargs["schema"]
        payload: dict[str, object] = {}
        for key in schema.get("required", []):
            if key == "google_title":
                payload[key] = "{FINISH_NAME} Skyline 18 Inch Towel Bar"
            elif key == "google_short_title":
                payload[key] = "18 Inch Towel Bar"
            elif key == "bing_title":
                payload[key] = "{FINISH_NAME} Skyline 18 Inch Towel Bar"
            elif key == "shopify_title":
                payload[key] = "Skyline Collection 18 Inch Towel Bar"
            elif key == "shopify_description":
                payload[key] = "Solid brass towel bar for daily bathroom storage."
            elif key == "shopify_meta_description":
                payload[key] = "Solid brass towel bar."
            elif key == "google_description":
                payload[key] = (
                    "Solid brass towel bar for daily storage. {FINISH_SENTENCE}"
                )
            elif key == "bing_description":
                payload[key] = (
                    "Solid brass towel bar for daily storage. {FINISH_SENTENCE}"
                )
            elif key == "finish_sentences":
                payload[key] = {
                    "Antique Brass": "Antique Brass complements this towel bar."
                }
        return payload


def _sample_parent_sku() -> ParentSKU:
    return ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        collection="Skyline",
        current_title="Skyline Collection 18 Inch Towel Bar",
        current_description="Solid brass wall-mounted towel bar for daily bathroom storage.",
        material="Solid Brass",
        mounting_type="Wall mount",
        variants=[
            Variant(
                option_sku="1031/18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_4542872518788_32118222192772",
                position=1,
            )
        ],
    )


def _query_context() -> QueryIntentSection:
    diagnostics = QueryIntentDiagnostics(
        query_intent_brief_enabled=True,
        query_intent_data_sufficiency=True,
        query_intent_primary_count=2,
        query_intent_source_query_count=4,
    )
    brief = QueryIntentBrief(
        primary_intents=["wall mounted towel bar", "solid brass towel bar"],
        title_emphasis=["wall mounted towel bar"],
        description_emphasis=["solid brass towel bar"],
        excluded_terms=[],
        data_sufficiency=True,
        reason_disabled=None,
        source_counts={
            "raw_master_queries": 4,
            "curated_master_queries": 3,
            "excluded_master_queries": 0,
        },
        diagnostics=diagnostics,
    )
    return QueryIntentSection(
        content="<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>",
        diagnostics=diagnostics,
        brief=brief,
    )


@pytest.mark.asyncio
async def test_execute_generation_bundle_builds_query_intent_once_for_google_bing(
    monkeypatch,
) -> None:
    provider = _FakeProvider()
    query_context_calls: list[str] = []

    monkeypatch.setattr(
        "feedops.generation.executor.build_evidence_table",
        lambda _sku: [],
    )
    monkeypatch.setattr(
        "feedops.generation.executor.filter_evidence_for_copy_context",
        lambda rows: rows,
    )
    monkeypatch.setattr(
        "feedops.generation.executor.format_evidence_markdown",
        lambda _rows, for_customer_copy=False: "table",
    )

    def _fake_query_context(parent_sku, evidence_rows, *, master_query_rows=None):
        query_context_calls.append(parent_sku.master_sku)
        return _query_context()

    monkeypatch.setattr(
        "feedops.generation.executor.build_query_intent_context",
        _fake_query_context,
    )

    bundle = await execute_generation_bundle(
        parent_sku=_sample_parent_sku(),
        provider=provider,
        selected_platforms=("google", "bing"),
        selected_content_types=("title",),
        request_id="req-query-intent-bundle",
    )

    assert query_context_calls == ["1031/18"]
    assert len(bundle.tasks) == 2
    assert len(bundle.results) == 2
    assert len(provider.calls) == 2
    assert all("<query_intent_brief>" in result.user_prompt for result in bundle.results)
    assert bundle.summary["query_intent_diagnostics"]["query_intent_brief_enabled"] is True


@pytest.mark.asyncio
async def test_execute_generation_bundle_skips_query_intent_for_shopify_only_scope(
    monkeypatch,
) -> None:
    provider = _FakeProvider()

    monkeypatch.setattr(
        "feedops.generation.executor.build_evidence_table",
        lambda _sku: [],
    )
    monkeypatch.setattr(
        "feedops.generation.executor.filter_evidence_for_copy_context",
        lambda rows: rows,
    )
    monkeypatch.setattr(
        "feedops.generation.executor.format_evidence_markdown",
        lambda _rows, for_customer_copy=False: "table",
    )

    def _unexpected_query_context(*_args, **_kwargs):
        raise AssertionError("query intent should not be built for shopify-only scope")

    monkeypatch.setattr(
        "feedops.generation.executor.build_query_intent_context",
        _unexpected_query_context,
    )

    bundle = await execute_generation_bundle(
        parent_sku=_sample_parent_sku(),
        provider=provider,
        selected_platforms=("shopify",),
        selected_content_types=("title",),
        request_id="req-query-intent-shopify",
    )

    assert len(bundle.tasks) == 1
    assert len(bundle.results) == 1
    assert len(provider.calls) == 1
    assert "<query_intent_brief>" not in bundle.results[0].user_prompt
    assert bundle.summary["query_intent_diagnostics"] == {}
