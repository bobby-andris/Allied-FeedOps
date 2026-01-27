"""Tests for Shopify catalog snapshot writer."""

from __future__ import annotations

import csv
from pathlib import Path


def test_write_shopify_catalog_csv_writes_expected_fields(monkeypatch, tmp_path):
    from feedops.integrations import shopify_catalog

    output_path = tmp_path / "catalog.csv"

    product = {
        "id": "gid://shopify/Product/4542872518788",
        "legacyResourceId": 4542872518788,
        "title": "Test Product",
        "descriptionHtml": "<p>Desc</p>",
        "productType": "Category A",
        "vendor": "Vendor",
        "tags": ["Brass", "Other"],
        "collections": {"nodes": [{"title": "Collection A"}]},
        "featuredMedia": {"image": {"url": "https://cdn.example.com/main.jpg"}},
        "metafields": {
            "nodes": [
                {
                    "namespace": "custom",
                    "key": "material",
                    "value": "Brass",
                    "type": "single_line_text_field",
                }
            ]
        },
        "variants": {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/32118222192772",
                    "legacyResourceId": 32118222192772,
                    "sku": "101-ABR",
                    "barcode": "12345",
                    "title": "Antique Brass",
                    "position": 1,
                    "selectedOptions": [{"name": "Finish", "value": "Antique Brass"}],
                    "media": {
                        "nodes": [
                            {"image": {"url": "https://cdn.example.com/variant.jpg"}}
                        ]
                    },
                }
            ]
        },
    }

    monkeypatch.setattr(
        shopify_catalog,
        "fetch_shopify_products",
        lambda *_args, **_kwargs: [product],
    )

    shopify_catalog.write_shopify_catalog_csv(output_path, limit=1)

    with output_path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        row = next(reader)

    def value(col: str) -> str:
        return row[header.index(col)]

    assert value("MasterSKU") == "101"
    assert value("OPTION SKU") == "101-ABR"
    assert value("GMCID") == "shopify_US_4542872518788_32118222192772"
    assert value("Finish") == "Antique Brass"
    assert value("Finish Code") == "ABR"
    assert value("Position") == "1"
    assert value("Category") == "Category A"
    assert value("Collection") == "Collection A"
    assert value("Title") == "Test Product"
    assert value("Narraive Copy") == "Desc"
    assert value("Material") == "Brass"
    assert value("Main URL") == "https://cdn.example.com/variant.jpg"
