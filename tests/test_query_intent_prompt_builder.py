from __future__ import annotations

from feedops.api.prompt_builder import build_core_prompt
from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.generation.tasks import build_task_prompt, task_prompt_hash
from feedops.models import ParentSKU, Variant
from feedops.pipeline.query_intent_brief import (
    QueryIntentBrief,
    QueryIntentDiagnostics,
    QueryIntentSection,
)


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


def _query_intent_context(content: str) -> QueryIntentSection:
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
        excluded_terms=["delta towel bar"],
        data_sufficiency=True,
        reason_disabled=None,
        source_counts={
            "raw_master_queries": 4,
            "curated_master_queries": 3,
            "excluded_master_queries": 1,
        },
        diagnostics=diagnostics,
    )
    return QueryIntentSection(content=content, diagnostics=diagnostics, brief=brief)


def _spec(kind: GenerationTaskKind, platform: str, content_type: str) -> TaskSpec:
    return TaskSpec(
        task_id=f"{platform}-{content_type}-{kind}",
        kind=kind,
        master_sku="1031/18",
        platform=platform,
        content_type=content_type,
        prompt_version="v2",
        request_id="req-query-intent",
        diagnostic_mode=False,
        cost_cap_usd=None,
    )


def test_build_core_prompt_includes_query_intent_brief_for_google_copy() -> None:
    prompt = build_core_prompt(
        _sample_parent_sku(),
        [],
        "Product Evidence Table",
        "google",
        "title",
        query_intent_section="<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>",
    )

    assert "<query_intent_brief>" in prompt
    assert "Never narrate what someone searched for." in prompt


def test_build_core_prompt_ignores_query_intent_brief_for_shopify_copy() -> None:
    prompt = build_core_prompt(
        _sample_parent_sku(),
        [],
        "Product Evidence Table",
        "shopify",
        "description",
        query_intent_section="<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>",
    )

    assert "<query_intent_brief>" not in prompt


def test_build_task_prompt_skips_query_intent_for_finish_sentences() -> None:
    prompt = build_task_prompt(
        _spec(GenerationTaskKind.FINISH_SENTENCES, "finish", "description"),
        parent_sku=_sample_parent_sku(),
        evidence=[],
        evidence_markdown="No evidence available.",
        query_intent_context=_query_intent_context(
            "<query_intent_brief>\n- should not appear\n</query_intent_brief>"
        ),
    )

    assert "<query_intent_brief>" not in prompt


def test_task_prompt_hash_changes_when_query_intent_brief_changes() -> None:
    context_a = _query_intent_context(
        "<query_intent_brief>\n- wall mounted towel bar\n</query_intent_brief>"
    )
    context_b = _query_intent_context(
        "<query_intent_brief>\n- solid brass towel bar\n</query_intent_brief>"
    )

    prompt_a = build_task_prompt(
        _spec(GenerationTaskKind.TITLE, "google", "title"),
        parent_sku=_sample_parent_sku(),
        evidence=[],
        evidence_markdown="No evidence available.",
        query_intent_context=context_a,
    )
    prompt_b = build_task_prompt(
        _spec(GenerationTaskKind.TITLE, "google", "title"),
        parent_sku=_sample_parent_sku(),
        evidence=[],
        evidence_markdown="No evidence available.",
        query_intent_context=context_b,
    )

    assert task_prompt_hash("system-google", prompt_a) != task_prompt_hash(
        "system-google",
        prompt_b,
    )
