from feedops.models import ParentSKU, Variant
from feedops.pipeline import evidence as evidence_module


def _sample_parent(collection: str | None):
    return ParentSKU(
        master_sku="TEST-2",
        category="Towel Bars",
        collection=collection,
        current_title="Sample Towel Bar",
        current_description="Sample description",
        variants=[
            Variant(
                option_sku="TEST-2-PC",
                finish="Polished Chrome",
                finish_code="PC",
                gmc_id="shopify_US_1_2",
            )
        ],
    )


def test_evidence_includes_collection_description_only_for_known_collections(monkeypatch):
    parent = _sample_parent(collection="Dottingham")

    monkeypatch.setattr(evidence_module, "is_known_collection_name", lambda _: True)
    monkeypatch.setattr(
        evidence_module,
        "get_collection_description",
        lambda _: "Classic collection language. Available in 28 finishes.",
    )
    monkeypatch.setattr(
        evidence_module,
        "sanitize_collection_description",
        lambda text: "Classic collection language.",
    )

    rows = evidence_module.build_evidence_table(parent)
    matches = [row for row in rows if row.field == "collection_description"]

    assert len(matches) == 1
    assert matches[0].value == "Classic collection language."
    assert matches[0].source == "collection_descriptions_csv"


def test_evidence_omits_collection_description_for_unknown_collection(monkeypatch):
    parent = _sample_parent(collection="Some Merchandising Bucket")

    monkeypatch.setattr(evidence_module, "is_known_collection_name", lambda _: False)

    rows = evidence_module.build_evidence_table(parent)
    matches = [row for row in rows if row.field == "collection_description"]

    assert matches == []

