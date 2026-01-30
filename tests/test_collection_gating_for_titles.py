from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant
from feedops.pipeline.enrichment import detect_collection
from feedops.pipeline.evidence import build_evidence_table


def _make_parent(*, master_sku: str, collection: str | None) -> ParentSKU:
    return ParentSKU(
        master_sku=master_sku,
        category="Accessories",
        collection=collection,
        current_title="Example Title",
        current_description="Example Description",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku=f"{master_sku}-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
            )
        ],
    )


def test_detect_collection_returns_none_for_unknown_collection_name():
    parent = _make_parent(master_sku="TEST-1", collection="Brass Paper Towel Holders")
    assert detect_collection(parent) is None


def test_evidence_table_omits_unknown_collection_fields(monkeypatch):
    # Avoid external keyword sources in unit tests.
    monkeypatch.setattr(
        "feedops.pipeline.evidence.get_external_keywords", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        "feedops.pipeline.evidence.fetch_master_sku_keywords",
        lambda *_args, **_kwargs: [],
    )

    parent = _make_parent(master_sku="TEST-2", collection="Brass Paper Towel Holders")
    evidence = build_evidence_table(parent)
    fields = {row.field for row in evidence}
    assert "collection" not in fields
    assert "collection_context" not in fields


def test_evidence_table_keeps_known_designer_collection(monkeypatch):
    monkeypatch.setattr(
        "feedops.pipeline.evidence.get_external_keywords", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        "feedops.pipeline.evidence.fetch_master_sku_keywords",
        lambda *_args, **_kwargs: [],
    )

    parent = _make_parent(master_sku="TEST-3", collection="Argo")
    evidence = build_evidence_table(parent)
    fields = {row.field for row in evidence}
    assert "collection" in fields
    assert "collection_context" in fields

