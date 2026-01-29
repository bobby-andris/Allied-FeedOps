import json

from feedops.quality.data_loader import load_exports_dir


def test_load_exports_dir_includes_variant_descriptions(tmp_path):
    patch = {
        "offerId": "shopify_US_parent",
        "title": "Base Title",
        "description": "Base Description",
        "variants": [
            {
                "offerId": "shopify_US_variant_1",
                "title": "Antique Brass Something, Allied Brass",
                "description": "Variant description in Antique Brass.",
                "_meta": {"finish": "Antique Brass", "option_sku": "SKU-ABR"},
            },
            {
                "offerId": "shopify_US_variant_2",
                "structured_title": {"content": "Satin Nickel Something, Allied Brass"},
                "structured_description": {"content": "Variant description in Satin Nickel."},
                "_meta": {"finish": "Satin Nickel", "option_sku": "SKU-SN"},
            },
        ],
        "_meta": {"quality_score": 88.0},
    }

    (tmp_path / "google-patch-TESTSKU.json").write_text(json.dumps(patch))

    exports = load_exports_dir(tmp_path)
    google = exports["TESTSKU"]["google"]
    assert len(google.variants) == 2
    assert google.variants[0]["_meta"]["finish"] == "Antique Brass"
    assert google.variants[0]["description"] == "Variant description in Antique Brass."
    assert google.variants[1]["_meta"]["finish"] == "Satin Nickel"
    assert google.variants[1]["title"] == "Satin Nickel Something, Allied Brass"
    assert google.variants[1]["description"] == "Variant description in Satin Nickel."

