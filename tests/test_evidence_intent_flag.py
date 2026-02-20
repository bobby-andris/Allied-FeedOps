from feedops.models import ParentSKU, Variant
from feedops.pipeline import evidence as evidence_module


def _sample_parent():
    return ParentSKU(
        master_sku="FLAG-1",
        category="Towel Bars",
        current_title="Solid Brass Towel Bar",
        current_description="desc",
        variants=[
            Variant(
                option_sku="FLAG-1-PC",
                finish="Polished Chrome",
                finish_code="PC",
                gmc_id="shopify_US_1_1",
            )
        ],
        merchant_center_items=[{"customLabel0": "towel bars"}],
    )


def test_build_evidence_uses_legacy_filter_when_intent_curator_flag_disabled(monkeypatch):
    parent = _sample_parent()

    monkeypatch.setattr(evidence_module, "is_intent_curator_v1_enabled", lambda: False)
    monkeypatch.setattr(evidence_module, "fetch_master_sku_keywords", lambda *a, **k: [])
    monkeypatch.setattr(evidence_module, "get_external_keywords", lambda *a, **k: [])
    monkeypatch.setattr(evidence_module, "fetch_search_queries_for_master_sku", lambda *a, **k: [{"query_text": "solid brass towel bar", "total_impressions": 100, "total_clicks": 10}])
    monkeypatch.setattr(evidence_module, "fetch_variant_queries_for_master_sku", lambda *a, **k: [{"query_text": "polished chrome towel bar", "impressions": 50, "clicks": 5, "finish_code": "PC"}])
    monkeypatch.setattr(evidence_module, "build_relevance_anchor_terms", lambda *a, **k: {"towel", "bar", "brass"})

    def _legacy_filter(rows, anchor_terms=None, min_keep=3):
        return rows

    monkeypatch.setattr(evidence_module, "filter_search_queries_by_relevance", _legacy_filter)

    def _should_not_run(*args, **kwargs):
        raise AssertionError("curate_search_queries_by_relevance should not be called when flag is disabled")

    monkeypatch.setattr(evidence_module, "curate_search_queries_by_relevance", _should_not_run)
    monkeypatch.setattr(evidence_module, "enrich_product", lambda *_: type("E", (), {"to_evidence_rows": lambda self: []})())

    rows = evidence_module.build_evidence_table(parent)
    fields = {row.field for row in rows}

    assert "search_queries_top" in fields
    assert "variant_top_queries" in fields
    assert "query_filter_kept_count" in fields
    assert "query_filter_dropped_count" in fields


def test_build_evidence_prefers_curator_when_flag_enabled(monkeypatch):
    parent = _sample_parent()

    monkeypatch.setattr(evidence_module, "is_intent_curator_v1_enabled", lambda: True)
    monkeypatch.setattr(evidence_module, "fetch_master_sku_keywords", lambda *a, **k: [])
    monkeypatch.setattr(evidence_module, "get_external_keywords", lambda *a, **k: [])
    monkeypatch.setattr(evidence_module, "fetch_search_queries_for_master_sku", lambda *a, **k: [{"query_text": "solid brass towel bar", "total_impressions": 100, "total_clicks": 10}])
    monkeypatch.setattr(evidence_module, "fetch_variant_queries_for_master_sku", lambda *a, **k: [{"query_text": "polished chrome towel bar", "impressions": 50, "clicks": 5, "finish_code": "PC"}])
    monkeypatch.setattr(evidence_module, "build_relevance_anchor_terms", lambda *a, **k: {"towel", "bar", "brass"})

    called = {"curator": 0}

    def _curator(rows, anchor_terms=None, min_keep=3, max_keep=12):
        called["curator"] += 1
        return rows[:max_keep], {
            "query_filter_kept_count": len(rows[:max_keep]),
            "query_filter_dropped_count": max(0, len(rows) - len(rows[:max_keep])),
            "query_filter_reason_top": "none",
        }

    monkeypatch.setattr(evidence_module, "curate_search_queries_by_relevance", _curator)

    def _legacy_should_not_run(*args, **kwargs):
        raise AssertionError("filter_search_queries_by_relevance should not be called when flag is enabled")

    monkeypatch.setattr(evidence_module, "filter_search_queries_by_relevance", _legacy_should_not_run)
    monkeypatch.setattr(evidence_module, "enrich_product", lambda *_: type("E", (), {"to_evidence_rows": lambda self: []})())

    rows = evidence_module.build_evidence_table(parent)
    fields = {row.field for row in rows}

    assert called["curator"] == 2
    assert "query_filter_reason_top" in fields
