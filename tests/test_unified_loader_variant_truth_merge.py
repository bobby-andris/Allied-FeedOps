from feedops.models import ParentSKU, Variant


def test_merge_catalog_variant_truth_preserves_shopify_content_and_adds_dimensions():
    from feedops.variant_truth import merge_catalog_variant_truth

    shopify_parent = ParentSKU(
        master_sku="QN-31/30",
        category="Towel Bars",
        collection="Some Shopify Collection",
        current_title="Shopify Title",
        current_description="Shopify description",
        material="Solid Brass",
        variants=[
            Variant(
                option_sku="QN-31-30-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
            )
        ],
        merchant_center_items=[{"offerId": "shopify_US_1_1"}],
        data_source="shopify_fresh",
    )

    catalog_parent = ParentSKU(
        master_sku="QN-31/30",
        category="Towel Bars",
        collection="Que New",
        current_title="Catalog Title",
        current_description="Catalog description",
        material="Brass",
        variants=[
            Variant(
                option_sku="QN-31/30-ABR",
                finish="Antique Brass",
                finish_code="ABR",
                gmc_id="shopify_US_1_1",
                product_length=30.0,
                product_height=3.0,
                projection=3.0,
                product_weight=3.2,
            )
        ],
    )

    merged = merge_catalog_variant_truth(shopify_parent, catalog_parent)
    assert merged.current_title == "Shopify Title"
    assert merged.current_description == "Shopify description"
    assert merged.collection == "Que New"
    assert merged.material == "Solid Brass"
    assert merged.merchant_center_items == [{"offerId": "shopify_US_1_1"}]
    assert merged.data_source == "shopify_fresh+csv_variant_truth"

    assert merged.variants[0].product_length == 30.0
