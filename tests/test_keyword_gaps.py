import pytest

from feedops.models import ParentSKU, Variant


def _make_parent_sku(*, title: str) -> ParentSKU:
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
        current_title=title,
        current_description="This stylish towel bar...",
        material="Brass",
        mounting_type="Wall mount",
        variants=[variant],
    )


def test_compute_keyword_gaps_for_title_ranks_and_filters_finish_specific_terms():
    from feedops.pipeline.keyword_gaps import compute_keyword_gaps_for_title

    parent_sku = _make_parent_sku(title="Skyline Collection 18 Inch Towel Bar")
    queries = [
        {"query_text": "bathroom towel bar wall mount", "avg_monthly_searches": 2400},
        {"query_text": "brass towel bar", "avg_monthly_searches": 1500},
        {"query_text": "18 inch towel bar", "avg_monthly_searches": 1200},
        # Finish-specific: should be excluded.
        {"query_text": "antique brass towel bar", "avg_monthly_searches": 2000},
        # Covered by title: should be excluded.
        {"query_text": "skyline towel bar", "avg_monthly_searches": 800},
    ]

    gaps = compute_keyword_gaps_for_title(parent_sku, queries, max_gaps=10)

    assert [g.query_text for g in gaps] == [
        "bathroom towel bar wall mount",
        "brass towel bar",
    ]
    assert gaps[0].metric.endswith(" vol")
    assert gaps[0].score >= gaps[1].score
    assert "bathroom" in gaps[0].missing_tokens


def test_compute_keyword_gaps_for_title_uses_impressions_when_volume_missing():
    from feedops.pipeline.keyword_gaps import compute_keyword_gaps_for_title

    parent_sku = _make_parent_sku(title="Skyline Collection Towel Bar")
    queries = [
        {"query_text": "bath towel holder", "total_impressions": 1500},
        {"query_text": "towel bar", "total_impressions": 1200},
    ]

    gaps = compute_keyword_gaps_for_title(parent_sku, queries, max_gaps=10)

    assert [g.query_text for g in gaps] == ["bath towel holder"]
    assert gaps[0].metric.endswith(" imp")


def test_build_keyword_gap_evidence_rows_formats_top_terms():
    from feedops.pipeline.keyword_gaps import build_keyword_gap_evidence_rows

    parent_sku = _make_parent_sku(title="Skyline Collection 18 Inch Towel Bar")
    queries = [
        {"query_text": "bathroom towel bar wall mount", "avg_monthly_searches": 2400},
        {"query_text": "brass towel bar", "avg_monthly_searches": 1500},
    ]

    evidence_rows = build_keyword_gap_evidence_rows(parent_sku, queries, max_gaps=5)

    assert len(evidence_rows) == 1
    row = evidence_rows[0]
    assert row.field == "keyword_gaps_current_title"
    assert '"bathroom towel bar wall mount"' in row.value
    assert "vol" in row.value
    assert row.source == "keyword_gaps"

