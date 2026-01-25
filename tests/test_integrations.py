import logging


def test_google_ads_keywords_disabled_returns_empty():
    from feedops.integrations.google_ads import fetch_high_performing_keywords

    assert fetch_high_performing_keywords("Towel Bars") == []


def test_google_ads_keywords_enabled_logs_warning(monkeypatch, caplog):
    from feedops.integrations.google_ads import fetch_high_performing_keywords

    monkeypatch.setenv("GOOGLE_ADS_MCP_ENABLED", "1")
    with caplog.at_level(logging.WARNING):
        result = fetch_high_performing_keywords("Towel Bars")
    assert result == []
    assert any("Google Ads MCP enabled" in record.message for record in caplog.records)


def test_google_ads_master_sku_keywords_api_enabled_returns_terms(monkeypatch):
    """When Google Ads API integration is enabled, return aggregated keyword phrases."""
    from feedops.integrations import google_ads

    monkeypatch.setenv("GOOGLE_ADS_API_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_ADS_CUSTOMER_ID", "1234567890")

    # Avoid real API/library calls in tests by injecting a fake fetcher.
    monkeypatch.setattr(google_ads, "_load_client", lambda: object(), raising=False)
    monkeypatch.setattr(
        google_ads,
        "_fetch_search_terms_for_item_ids",
        lambda *args, **kwargs: [
            {"term": "wall mount towel bar", "clicks": 10, "impressions": 100, "conversions": 1.0},
            {"term": "bath towel holder", "clicks": 7, "impressions": 80, "conversions": 0.0},
            {"term": "wall mount towel bar", "clicks": 3, "impressions": 40, "conversions": 0.0},
        ],
        raising=False,
    )

    keywords = google_ads.fetch_master_sku_keywords(
        "4542872518788",
        item_ids=["shopify_US_4542872518788_32118222192772"],
        category="Towel Bars",
    )

    assert keywords[:2] == ["wall mount towel bar", "bath towel holder"]


def test_google_ads_normalizes_item_ids_for_ads():
    """Listing group item IDs are normalized for case-insensitive matching."""
    from feedops.integrations import google_ads

    assert google_ads._normalize_item_ids_for_ads(
        ["shopify_US_12345", "  SHOPIFY_us_98765  "]
    ) == ["shopify_us_12345", "shopify_us_98765"]


def test_analytics_metrics_disabled_returns_none():
    from feedops.integrations.analytics import fetch_product_metrics

    assert fetch_product_metrics("101") is None


def test_analytics_metrics_enabled_logs_warning(monkeypatch, caplog):
    from feedops.integrations.analytics import fetch_product_metrics

    monkeypatch.setenv("ANALYTICS_MCP_ENABLED", "1")
    with caplog.at_level(logging.WARNING):
        result = fetch_product_metrics("101")
    assert result is None
    assert any("Analytics MCP enabled" in record.message for record in caplog.records)


def test_apify_competitors_disabled_returns_empty():
    from feedops.integrations.apify import fetch_competitor_titles

    assert fetch_competitor_titles("Towel Bars") == []


def test_apify_competitors_enabled_logs_warning(monkeypatch, caplog):
    from feedops.integrations.apify import fetch_competitor_titles

    monkeypatch.setenv("APIFY_MCP_ENABLED", "1")
    with caplog.at_level(logging.WARNING):
        result = fetch_competitor_titles("Towel Bars")
    assert result == []
    assert any("Apify MCP enabled" in record.message for record in caplog.records)
