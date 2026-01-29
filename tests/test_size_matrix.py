from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant

from feedops.pipeline.size_matrix import build_size_matrix, get_variant_size_label


def test_build_size_matrix_groups_by_size_from_option_sku() -> None:
    parent = ParentSKU(
        master_sku="CL-41-18",
        category="Towel Bars",
        current_title="x",
        current_description="x",
        variants=[
            Variant(
                option_sku="CL-41-18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
                product_length=20,
                product_width=2,
                product_height=3.5,
                product_weight=2.4,
                projection=2,
            ),
            Variant(
                option_sku="CL-41-36-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_2",
                product_length=36,
                product_width=2,
                product_height=3.5,
                product_weight=4,
                projection=2,
            ),
        ],
    )
    matrix = build_size_matrix(parent)
    assert [row["size_label"] for row in matrix] == ["18 Inch", "36 Inch"]
    assert matrix[0]["overall"] == "20 × 2 × 3.5 in"
    assert matrix[1]["weight_lb"] == "4"


def test_build_size_matrix_filters_unparseable_or_implausible_sizes() -> None:
    parent = ParentSKU(
        master_sku="CM-P-700-36-GB",
        category="Towel Bars",
        current_title="x",
        current_description="x",
        variants=[
            Variant(
                option_sku="CM-P-700-36-GB",
                finish="Gold Brushed",
                finish_code="GB",
                gmc_id="shopify_US_2_1",
                product_length=36,
            ),
            # If we couldn't remove finish code, we'd accidentally treat 700 as a size.
            Variant(
                option_sku="CM-P-700-GB",
                finish="Gold Brushed",
                finish_code="GB",
                gmc_id="shopify_US_2_2",
                product_length=0,
            ),
        ],
    )
    matrix = build_size_matrix(parent)
    assert [row["size_label"] for row in matrix] == ["36 Inch"]


def test_build_size_matrix_parses_slash_style_master_skus() -> None:
    parent = ParentSKU(
        master_sku="1031/18",
        category="Towel Bars",
        current_title="x",
        current_description="x",
        variants=[
            Variant(
                option_sku="1031/18-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_3_1",
                product_length=18,
            ),
            Variant(
                option_sku="1031/36-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_3_2",
                product_length=36,
            ),
        ],
    )
    matrix = build_size_matrix(parent)
    assert [row["size_label"] for row in matrix] == ["18 Inch", "36 Inch"]


def test_get_variant_size_label_returns_normalized_label() -> None:
    variant = Variant(
        option_sku="1031/36-ABR",
        finish="Antique Brass",
        finish_code="ABR",
        gmc_id="shopify_US_9_9",
    )
    assert get_variant_size_label(variant) == "36 Inch"
