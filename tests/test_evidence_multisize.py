from feedops.models import ParentSKU, Variant
from feedops.pipeline.evidence import build_evidence_table


def test_evidence_includes_available_sizes_and_omits_single_length_for_multi_size_products():
    parent = ParentSKU(
        master_sku="CL-41",
        category="Towel Bars",
        collection="Carolina",
        current_title="Current",
        current_description="Current",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku="CL-41-18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_18",
                product_length=18.0,
            ),
            Variant(
                option_sku="CL-41-24-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_24",
                product_length=24.0,
            ),
        ],
    )

    evidence = build_evidence_table(parent)
    fields = {e.field: e.value for e in evidence}

    assert "available_sizes" in fields
    assert "18" in str(fields["available_sizes"])
    assert "24" in str(fields["available_sizes"])

    # For multi-size products, avoid injecting a single variant length as if it applies to all variants.
    assert "product_length" not in fields

