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
