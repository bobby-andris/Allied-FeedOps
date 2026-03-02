from __future__ import annotations

from feedops.models import ParentSKU, Variant
from feedops.pipeline.feature_flags import capture_flag_snapshot
from feedops.pipeline.query_intent_brief import (
    build_query_intent_brief,
    build_query_intent_context,
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


def _query_row(
    query_text: str,
    *,
    impressions: float = 120.0,
    clicks: float = 15.0,
    conversions: float = 2.0,
    conversion_value: float = 180.0,
    avg_monthly_searches: float = 40.0,
) -> dict[str, object]:
    return {
        "query_text": query_text,
        "total_impressions": impressions,
        "total_clicks": clicks,
        "total_conversions": conversions,
        "total_conversion_value": conversion_value,
        "avg_monthly_searches": avg_monthly_searches,
    }


def test_capture_flag_snapshot_includes_query_intent_brief_flag(monkeypatch) -> None:
    monkeypatch.delenv("QUERY_INTENT_BRIEF_V1", raising=False)
    assert capture_flag_snapshot()["QUERY_INTENT_BRIEF_V1"] is False

    monkeypatch.setenv("QUERY_INTENT_BRIEF_V1", "1")
    assert capture_flag_snapshot()["QUERY_INTENT_BRIEF_V1"] is True


def test_build_query_intent_brief_filters_noise_and_bounds_output() -> None:
    parent = _sample_parent_sku()
    master_query_rows = [
        _query_row("wall mounted brass towel bar", conversion_value=220.0),
        _query_row("solid brass towel bar", conversion_value=210.0),
        _query_row("bath towel holder brass", conversion_value=205.0),
        _query_row("delta towel bar", conversion_value=250.0),
        _query_row("ada compliant towel bar", conversion_value=240.0),
        _query_row("antique brass towel bar", conversion_value=230.0),
        _query_row("towel bar installation instructions", conversion_value=50.0),
    ]

    brief = build_query_intent_brief(
        parent,
        [],
        master_query_rows=master_query_rows,
    )

    assert brief.data_sufficiency is True
    assert brief.reason_disabled is None
    assert len(brief.primary_intents) <= 3
    assert len(brief.title_emphasis) <= 3
    assert len(brief.description_emphasis) <= 3
    assert len(brief.excluded_terms) <= 5
    assert brief.source_counts["curated_master_queries"] >= 3
    assert "delta towel bar" in brief.excluded_terms
    assert "ada compliant towel bar" in brief.excluded_terms
    assert "antique brass towel bar" in brief.excluded_terms
    assert "towel bar installation instructions" in brief.excluded_terms

    primary_text = " ".join(brief.primary_intents).lower()
    assert "delta" not in primary_text
    assert "ada" not in primary_text
    assert "antique brass" not in primary_text

    repeated = build_query_intent_brief(
        parent,
        [],
        master_query_rows=master_query_rows,
    )
    assert repeated.primary_intents == brief.primary_intents
    assert repeated.title_emphasis == brief.title_emphasis
    assert repeated.description_emphasis == brief.description_emphasis
    assert repeated.excluded_terms == brief.excluded_terms


def test_build_query_intent_brief_disables_when_signal_is_weak() -> None:
    parent = _sample_parent_sku()
    brief = build_query_intent_brief(
        parent,
        [],
        master_query_rows=[
            _query_row(
                "wall mounted towel bar",
                impressions=5.0,
                clicks=0.0,
                conversions=0.0,
                conversion_value=0.0,
                avg_monthly_searches=1.0,
            ),
            _query_row(
                "brass towel holder",
                impressions=4.0,
                clicks=0.0,
                conversions=0.0,
                conversion_value=0.0,
                avg_monthly_searches=1.0,
            ),
        ],
    )

    assert brief.data_sufficiency is False
    assert brief.reason_disabled == "insufficient_query_signal"
    assert brief.diagnostics.query_intent_brief_enabled is False


def test_build_query_intent_context_honors_feature_flag(monkeypatch) -> None:
    monkeypatch.delenv("QUERY_INTENT_BRIEF_V1", raising=False)

    context = build_query_intent_context(
        _sample_parent_sku(),
        [],
        master_query_rows=[_query_row("wall mounted brass towel bar")],
    )

    assert context.content == ""
    assert context.diagnostics.query_intent_disabled_reason == "feature_flag_disabled"
