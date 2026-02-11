from __future__ import annotations


def test_build_competitor_evidence_separates_direct_vs_marketplace_listings(monkeypatch):
    from feedops.pipeline import competitor_evidence

    sample_listings = [
        {
            "source": "google",
            "source_type": "serp",
            "domain": "build.com",
            "brand": "Delta",
            "title": "24-Inch Towel Bar - Build.com",
            "position": 1,
        },
        {
            "source": "amazon",
            "source_type": "marketplace",
            "domain": "www.amazon.com",
            "brand": "Generic",
            "title": "Towel Bar 24 Inch Wall Mounted",
            "position": 3,
        },
        {
            "source": "google",
            "source_type": "serp",
            "domain": "https://www.wayfair.com/some/product",
            "brand": "Moen",
            "title": "Modern Towel Bar",
            "position": 2,
        },
        {
            "source": "google",
            "source_type": "serp",
            "domain": None,
            "brand": None,
            "title": "Towel Bar",
            "position": None,
        },
    ]

    monkeypatch.setattr(
        competitor_evidence,
        "_fetch_competitor_listings",
        lambda *args, **kwargs: sample_listings,
    )
    monkeypatch.setattr(
        competitor_evidence,
        "_fetch_competitor_patterns",
        lambda *args, **kwargs: [],
    )

    result = competitor_evidence.build_competitor_evidence("Towel Bars", client=object())

    assert result.category == "Towel Bars"
    assert result.direct.listing_count == 1  # build.com
    assert result.marketplace.listing_count == 2  # amazon + wayfair
    assert result.unknown.listing_count == 1  # no domain

    assert [x.name for x in result.direct.top_domains] == ["build.com"]
    assert [x.name for x in result.marketplace.top_domains] == ["amazon.com", "wayfair.com"]


def test_build_competitor_evidence_classifies_patterns_by_sources(monkeypatch):
    from feedops.pipeline import competitor_evidence

    sample_patterns = [
        {
            "pattern_type": "keyword",
            "pattern_value": "wall mount",
            "frequency": 10,
            "avg_position": 4.2,
            "sources": ["build.com", "signaturehardware.com"],
            "example_titles": ["24-Inch Wall Mount Towel Bar"],
        },
        {
            "pattern_type": "keyword",
            "pattern_value": "prime",
            "frequency": 7,
            "avg_position": 7.1,
            "sources": ["amazon.com"],
            "example_titles": ["Prime Eligible Towel Bar"],
        },
        {
            "pattern_type": "benefit",
            "pattern_value": "easy installation",
            "frequency": 3,
            "avg_position": None,
            "sources": ["amazon.com", "build.com"],
            "example_titles": [],
        },
        {
            "pattern_type": "trust_signal",
            "pattern_value": "lifetime warranty",
            "frequency": 2,
            "avg_position": None,
            "sources": None,
            "example_titles": None,
        },
    ]

    monkeypatch.setattr(
        competitor_evidence,
        "_fetch_competitor_listings",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        competitor_evidence,
        "_fetch_competitor_patterns",
        lambda *args, **kwargs: sample_patterns,
    )

    result = competitor_evidence.build_competitor_evidence("Towel Bars", client=object())

    assert [p.pattern_value for p in result.direct.patterns] == ["wall mount"]
    assert [p.pattern_value for p in result.marketplace.patterns] == ["prime"]
    assert [p.pattern_value for p in result.mixed.patterns] == ["easy installation"]
    assert [p.pattern_value for p in result.unknown.patterns] == ["lifetime warranty"]


def test_normalize_domain_and_marketplace_detection_are_boundary_safe():
    from feedops.pipeline import competitor_evidence

    assert competitor_evidence.normalize_domain("www.amazon.com") == "amazon.com"
    assert (
        competitor_evidence.normalize_domain("https://www.wayfair.com/some/product") == "wayfair.com"
    )

    # Ensure we don't misclassify "notamazon.com" as a marketplace.
    assert competitor_evidence._is_marketplace_domain(
        "seller.amazon.com", competitor_evidence._DEFAULT_MARKETPLACE_DOMAINS
    )
    assert not competitor_evidence._is_marketplace_domain(
        "notamazon.com", competitor_evidence._DEFAULT_MARKETPLACE_DOMAINS
    )
