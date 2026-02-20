from feedops.models import ParentSKU, Variant
from feedops.pipeline.evidence import build_evidence_table


def _sample_parent(**overrides):
    parent = ParentSKU(
        master_sku="TEST-1",
        category="Towel Bars",
        current_title="Sample Towel Bar",
        current_description="Sample description",
        variants=[
            Variant(
                option_sku="TEST-1-PC",
                finish="Polished Chrome",
                finish_code="PC",
                gmc_id="shopify_US_1_1",
            )
        ],
        **overrides,
    )
    return parent


def test_evidence_includes_custom_label_0_from_merchant_center_items():
    parent = _sample_parent(
        merchant_center_items=[
            {"customLabel0": "wall mounted towel bars"},
            {"custom_label_0": "wall mounted towel bars"},
            {"attributes": {"customLabel0": "paper towel holders"}},
        ]
    )

    rows = build_evidence_table(parent)
    custom_label_rows = [r for r in rows if r.field == "custom_label_0"]

    assert len(custom_label_rows) == 1
    assert custom_label_rows[0].source == "merchant_center_items.customLabel0"
    assert custom_label_rows[0].value == "wall mounted towel bars, paper towel holders"

