from feedops.models import ParentSKU, Variant
from feedops.pipeline.size_matrix import build_size_matrix


def test_build_size_matrix_uses_dimensions_when_present():
    parent = ParentSKU(
        master_sku="TB-TEST",
        category="Towel Bars",
        collection="Test",
        current_title="Test",
        current_description="Test",
        material="Brass",
        variants=[
            Variant(
                option_sku="TB-TEST-18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
                product_length=18.0,
            ),
            Variant(
                option_sku="TB-TEST-24-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_2",
                product_length=24.0,
            ),
        ],
    )

    matrix = build_size_matrix(parent)
    assert [row["size_label"] for row in matrix] == ["18 Inch", "24 Inch"]


def test_build_size_matrix_returns_empty_when_no_dimension_variance():
    parent = ParentSKU(
        master_sku="MB-20",
        category="Robe Hooks",
        collection="Malibu",
        current_title="Robe Hook",
        current_description="Test",
        material="Brass",
        variants=[
            Variant(
                option_sku="MB-20-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_2_1",
                product_length=2.0,
                product_width=2.64,
                projection=2.64,
            ),
            Variant(
                option_sku="MB-20-ABZ",
                finish="Antique Bronze",
                finish_code="ABZ",
                gmc_id="shopify_US_2_2",
                product_length=2.0,
                product_width=2.64,
                projection=2.64,
            ),
        ],
    )

    matrix = build_size_matrix(parent)
    assert matrix == []

