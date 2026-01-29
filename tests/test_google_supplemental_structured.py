from feedops.integrations.google_supplemental import generate_supplemental_feed


def test_generate_supplemental_feed_structured_only_emits_structured_fields(
    monkeypatch,
):
    monkeypatch.setenv("FEEDOPS_GMC_STRUCTURED_ONLY", "true")

    patch = {
        "offerId": "shopify_US_1_1",
        "title": "Fallback Title",
        "short_title": "Short Overlay Title",
        "description": "Fallback Description",
        "structured_title": {
            "digital_source_type": "trained_algorithmic_media",
            "content": "Structured Title",
        },
        "structured_description": {
            "digital_source_type": "trained_algorithmic_media",
            "content": "Structured Description",
        },
        "variants": [],
    }

    xml = generate_supplemental_feed([patch], environment="staging", include_variants=False)

    assert "<g:structured_title>" in xml
    assert "<g:structured_description>" in xml
    assert "Structured Title" in xml
    assert "Structured Description" in xml
    assert "<g:short_title>" in xml
    assert "Short Overlay Title" in xml

    assert "<g:title>" not in xml
    assert "<g:description>" not in xml
