"""Tests for data collection workers.

Validates that all 4 collection worker functions:
- Call existing client libraries correctly
- Use idempotent upserts (ON CONFLICT)
- Handle edge cases (empty results, missing data)
- Return correct result shape (list[dict] with item_id and status)
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4


# =============================================================================
# Google Ads Workers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_collect_search_terms_batch_calls_client():
    """Test search terms worker calls SearchTermsClient and saves with idempotent upserts."""
    from feedops.jobs.workers import collect_search_terms_batch

    # Mock dependencies - patch at import location
    with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockClient, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        # Setup mocks
        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance

        # Mock fetch_search_terms to return sample data
        mock_client_instance.fetch_search_terms.return_value = [
            {"query_text": "brass towel bar", "master_sku": "SKU-1", "impressions": 100},
            {"query_text": "bathroom hardware", "master_sku": "SKU-2", "impressions": 50},
            {"query_text": "wall mount hooks", "master_sku": "SKU-1", "impressions": 75},
        ]

        # Mock save_search_terms_to_db to return count
        mock_client_instance.save_search_terms_to_db.return_value = 2

        # Call worker
        batch = ["SKU-1", "SKU-2"]
        results = await collect_search_terms_batch(batch)

        # Assert: fetch_search_terms called with days=180
        mock_client_instance.fetch_search_terms.assert_called_once()
        call_kwargs = mock_client_instance.fetch_search_terms.call_args[1]
        assert call_kwargs["days"] == 180
        assert call_kwargs["limit"] == 10000

        # Assert: save_search_terms_to_db called with filtered results
        mock_client_instance.save_search_terms_to_db.assert_called_once()
        save_call_kwargs = mock_client_instance.save_search_terms_to_db.call_args[1]

        # Should only include terms for SKU-1 and SKU-2 (filtered from fetch results)
        saved_terms = save_call_kwargs["search_terms"]
        assert len(saved_terms) == 3  # All 3 terms are for SKU-1 or SKU-2
        assert all(term["master_sku"] in batch for term in saved_terms)

        # Assert: Returns list of dicts with item_id and status
        assert len(results) == 2
        assert all("item_id" in r and "status" in r for r in results)

        # Verify SKU-1 has terms_count=2
        sku1_result = [r for r in results if r["item_id"] == "SKU-1"][0]
        assert sku1_result["status"] == "ok"
        assert sku1_result["terms_count"] == 2

        # Verify SKU-2 has terms_count=1
        sku2_result = [r for r in results if r["item_id"] == "SKU-2"][0]
        assert sku2_result["status"] == "ok"
        assert sku2_result["terms_count"] == 1


@pytest.mark.asyncio
async def test_collect_search_terms_batch_empty_results():
    """Test search terms worker handles empty results gracefully."""
    from feedops.jobs.workers import collect_search_terms_batch

    with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockClient, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance

        # Mock empty results
        mock_client_instance.fetch_search_terms.return_value = []

        # Call worker
        results = await collect_search_terms_batch(["SKU-1"])

        # Assert: Returns result with status "no_data"
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "no_data"

        # Assert: save_search_terms_to_db NOT called (no data to save)
        mock_client_instance.save_search_terms_to_db.assert_not_called()


@pytest.mark.asyncio
async def test_collect_search_terms_batch_filters_by_sku():
    """Test search terms worker filters results to only requested SKUs."""
    from feedops.jobs.workers import collect_search_terms_batch

    with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockClient, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        mock_client_instance = MagicMock()
        MockClient.return_value = mock_client_instance

        # Mock fetch_search_terms to return terms for SKU-1, SKU-2, SKU-3
        mock_client_instance.fetch_search_terms.return_value = [
            {"query_text": "term1", "master_sku": "SKU-1", "impressions": 100},
            {"query_text": "term2", "master_sku": "SKU-2", "impressions": 50},
            {"query_text": "term3", "master_sku": "SKU-3", "impressions": 75},
        ]

        mock_client_instance.save_search_terms_to_db.return_value = 2

        # Call worker with only SKU-1 and SKU-2 (filtering out SKU-3)
        batch = ["SKU-1", "SKU-2"]
        results = await collect_search_terms_batch(batch)

        # Assert: Only terms for SKU-1 and SKU-2 are saved (SKU-3 filtered out)
        save_call_kwargs = mock_client_instance.save_search_terms_to_db.call_args[1]
        saved_terms = save_call_kwargs["search_terms"]
        assert len(saved_terms) == 2
        assert all(term["master_sku"] in batch for term in saved_terms)
        assert not any(term["master_sku"] == "SKU-3" for term in saved_terms)


@pytest.mark.asyncio
async def test_collect_performance_batch_aggregates_variants():
    """Test performance worker aggregates variant-level metrics to master_sku level."""
    from feedops.jobs.workers import collect_performance_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_performance.fetch_batch_product_performance") as mock_fetch, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query to return 3 variants for SKU-1
        mock_variant_result = MagicMock()
        mock_variant_result.data = [
            {"gmc_offer_id": "shopify_us_123_456"},
            {"gmc_offer_id": "shopify_us_123_457"},
            {"gmc_offer_id": "shopify_us_123_458"},
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_variant_result

        # Mock fetch_batch_product_performance to return metrics for each variant
        mock_fetch.return_value = {
            "shopify_us_123_456": {
                "impressions": 1000,
                "clicks": 50,
                "conversions": 5,
                "conversion_value": 500.0,
                "cost": 100.0,
            },
            "shopify_us_123_457": {
                "impressions": 2000,
                "clicks": 100,
                "conversions": 10,
                "conversion_value": 1000.0,
                "cost": 200.0,
            },
            "shopify_us_123_458": {
                "impressions": 3000,
                "clicks": 150,
                "conversions": 15,
                "conversion_value": 1500.0,
                "cost": 300.0,
            },
        }

        # Mock upsert
        mock_upsert = MagicMock()
        mock_upsert.execute.return_value = MagicMock()
        mock_supabase.table.return_value.upsert.return_value = mock_upsert

        # Call worker
        results = await collect_performance_batch(["SKU-1"])

        # Assert: fetch_batch_product_performance called with all 3 offer_ids
        mock_fetch.assert_called_once()
        call_kwargs = mock_fetch.call_args[1]
        assert len(call_kwargs["offer_ids"]) == 3
        assert "shopify_us_123_456" in call_kwargs["offer_ids"]
        assert "shopify_us_123_457" in call_kwargs["offer_ids"]
        assert "shopify_us_123_458" in call_kwargs["offer_ids"]

        # Assert: Upsert called with aggregated metrics
        mock_upsert_call = mock_supabase.table.return_value.upsert.call_args
        upsert_data = mock_upsert_call[0][0]

        # Total impressions should be sum of all variants: 1000 + 2000 + 3000 = 6000
        # Avg impressions = 6000 / 180 days
        assert upsert_data["master_sku"] == "SKU-1"
        assert upsert_data["platform"] == "google"

        # Verify aggregated totals
        expected_total_impressions = 6000
        expected_total_clicks = 300
        expected_avg_impressions = 6000 / 180
        expected_avg_clicks = 300 / 180

        assert abs(upsert_data["avg_impressions"] - expected_avg_impressions) < 0.01
        assert abs(upsert_data["avg_clicks"] - expected_avg_clicks) < 0.01

        # Assert: Upsert uses on_conflict="master_sku,platform"
        upsert_kwargs = mock_upsert_call[1]
        assert upsert_kwargs["on_conflict"] == "master_sku,platform"

        # Assert: Returns result with item_id and status
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "ok"
        assert results[0]["impressions"] == 6000
        assert results[0]["clicks"] == 300


@pytest.mark.asyncio
async def test_collect_performance_batch_no_variants():
    """Test performance worker handles SKUs with no variants gracefully."""
    from feedops.jobs.workers import collect_performance_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_performance.fetch_batch_product_performance") as mock_fetch, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query to return empty result
        mock_variant_result = MagicMock()
        mock_variant_result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_variant_result

        # Call worker
        results = await collect_performance_batch(["SKU-1"])

        # Assert: Returns result with status "no_data"
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "no_data"

        # Assert: fetch_batch_product_performance NOT called
        mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_collect_performance_batch_includes_timestamps():
    """Test performance worker includes timestamps and date range fields."""
    from feedops.jobs.workers import collect_performance_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_performance.fetch_batch_product_performance") as mock_fetch, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query
        mock_variant_result = MagicMock()
        mock_variant_result.data = [{"gmc_offer_id": "shopify_us_123_456"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_variant_result

        # Mock fetch_batch_product_performance
        mock_fetch.return_value = {
            "shopify_us_123_456": {
                "impressions": 1000,
                "clicks": 50,
                "conversions": 5,
                "conversion_value": 500.0,
                "cost": 100.0,
            }
        }

        # Mock upsert
        mock_upsert = MagicMock()
        mock_upsert.execute.return_value = MagicMock()
        mock_supabase.table.return_value.upsert.return_value = mock_upsert

        # Call worker
        results = await collect_performance_batch(["SKU-1"])

        # Assert: Upsert data includes baseline_start_date and baseline_end_date (DATA-05)
        upsert_call = mock_supabase.table.return_value.upsert.call_args
        upsert_data = upsert_call[0][0]

        assert "baseline_start_date" in upsert_data
        assert "baseline_end_date" in upsert_data
        assert upsert_data["baseline_start_date"] == "2025-08-01"
        assert upsert_data["baseline_end_date"] == "2026-01-28"

        # Note: created_at is auto-populated by DB default (DATA-10), not in upsert data


# =============================================================================
# Keyword Planner and Custom Labels Workers Tests
# =============================================================================


@pytest.mark.asyncio
async def test_collect_keyword_planner_batch_builds_seeds():
    """Test keyword planner worker builds seeds from product_title and top search terms."""
    from feedops.jobs.workers import collect_keyword_planner_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_search_terms.KeywordPlannerClient") as MockKPClient:

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query to return product_title
        mock_variant_result = MagicMock()
        mock_variant_result.data = [{"product_title": "Brass Towel Bar 24 inch"}]

        # Mock search_queries query to return top 3 search terms
        mock_search_result = MagicMock()
        mock_search_result.data = [
            {"query_text": "brass towel bar", "impressions": 100},
            {"query_text": "bathroom hardware", "impressions": 50},
            {"query_text": "wall mount hooks", "impressions": 25},
        ]

        # Setup query chain
        def select(columns):
            select_mock = MagicMock()
            eq_mock = MagicMock()

            if "product_title" in columns:
                # variant_index query
                limit_mock = MagicMock()
                limit_mock.execute.return_value = mock_variant_result
                eq_mock.limit.return_value = limit_mock
            else:
                # search_queries query
                order_mock = MagicMock()
                limit_mock = MagicMock()
                limit_mock.execute.return_value = mock_search_result
                order_mock.limit.return_value = limit_mock
                eq_mock.order.return_value = order_mock

            select_mock.eq.return_value = eq_mock
            return select_mock

        mock_supabase.table.return_value.select = select

        # Mock KeywordPlannerClient
        mock_kp_instance = MagicMock()
        MockKPClient.return_value = mock_kp_instance
        mock_kp_instance.get_historical_metrics.return_value = [
            {"keyword": "Brass Towel Bar 24 inch", "avg_monthly_searches": 1000},
            {"keyword": "brass towel bar", "avg_monthly_searches": 5000},
            {"keyword": "bathroom hardware", "avg_monthly_searches": 2000},
            {"keyword": "wall mount hooks", "avg_monthly_searches": 1500},
        ]

        # Call worker
        results = await collect_keyword_planner_batch(["SKU-1"])

        # Assert: get_historical_metrics called with product_title + top search terms
        mock_kp_instance.get_historical_metrics.assert_called_once()
        call_kwargs = mock_kp_instance.get_historical_metrics.call_args[1]

        keywords = call_kwargs["keywords"]
        assert "Brass Towel Bar 24 inch" in keywords  # product_title
        assert "brass towel bar" in keywords  # top search term 1
        assert "bathroom hardware" in keywords  # top search term 2
        assert "wall mount hooks" in keywords  # top search term 3

        # Assert: use_cache=True and cache_max_age_days=30 passed
        assert call_kwargs["use_cache"] is True
        assert call_kwargs["cache_max_age_days"] == 30

        # Assert: Returns result with keywords_enriched count
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "ok"
        assert results[0]["keywords_enriched"] == 4


@pytest.mark.asyncio
async def test_collect_keyword_planner_batch_no_product_title():
    """Test keyword planner worker handles missing product_title gracefully."""
    from feedops.jobs.workers import collect_keyword_planner_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_search_terms.KeywordPlannerClient") as MockKPClient:

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query to return record with NULL product_title
        mock_variant_result = MagicMock()
        mock_variant_result.data = [{"product_title": None}]

        select_mock = MagicMock()
        eq_mock = MagicMock()
        limit_mock = MagicMock()
        limit_mock.execute.return_value = mock_variant_result
        eq_mock.limit.return_value = limit_mock
        select_mock.eq.return_value = eq_mock
        mock_supabase.table.return_value.select.return_value = select_mock

        # Call worker
        results = await collect_keyword_planner_batch(["SKU-1"])

        # Assert: Returns result with status "no_data"
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "no_data"


@pytest.mark.asyncio
async def test_collect_keyword_planner_batch_returns_enrichment_count():
    """Test keyword planner worker returns keywords_enriched count."""
    from feedops.jobs.workers import collect_keyword_planner_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_search_terms.KeywordPlannerClient") as MockKPClient:

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock variant_index query
        mock_variant_result = MagicMock()
        mock_variant_result.data = [{"product_title": "Test Product"}]

        # Mock search_queries query (empty)
        mock_search_result = MagicMock()
        mock_search_result.data = []

        # Setup query chain
        def select(columns):
            select_mock = MagicMock()
            eq_mock = MagicMock()

            if "product_title" in columns:
                limit_mock = MagicMock()
                limit_mock.execute.return_value = mock_variant_result
                eq_mock.limit.return_value = limit_mock
            else:
                order_mock = MagicMock()
                limit_mock = MagicMock()
                limit_mock.execute.return_value = mock_search_result
                order_mock.limit.return_value = limit_mock
                eq_mock.order.return_value = order_mock

            select_mock.eq.return_value = eq_mock
            return select_mock

        mock_supabase.table.return_value.select = select

        # Mock KeywordPlannerClient to return 5 enriched keywords
        mock_kp_instance = MagicMock()
        MockKPClient.return_value = mock_kp_instance
        mock_kp_instance.get_historical_metrics.return_value = [
            {"keyword": f"keyword_{i}", "avg_monthly_searches": 100 * i}
            for i in range(1, 6)
        ]

        # Call worker
        results = await collect_keyword_planner_batch(["SKU-1"])

        # Assert: Result includes keywords_enriched count
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "ok"
        assert results[0]["keywords_enriched"] == 5


@pytest.mark.asyncio
async def test_collect_custom_labels_batch_syncs_labels():
    """Test custom labels worker syncs labels from GMC and calls API only once per batch."""
    from feedops.jobs.workers import collect_custom_labels_batch

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.merchant_center.fetch_merchant_center_items") as mock_fetch_gmc:

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock fetch_merchant_center_items to return items with custom labels
        mock_fetch_gmc.return_value = [
            {
                "offerId": "shopify_US_123_456",
                "customLabel0": "category:bathroom",
                "customLabel1": "finish:brass",
                "customLabel2": "price_tier:mid",
                "customLabel3": "stock:in_stock",
                "customLabel4": "new:no",
            },
            {
                "offerId": "shopify_US_123_457",
                "customLabel0": "category:bathroom",
                "customLabel1": "finish:chrome",
                "customLabel2": "price_tier:mid",
                "customLabel3": "stock:in_stock",
                "customLabel4": "new:no",
            },
        ]

        # Mock variant_index query to return offer_ids for SKU-1 and SKU-2
        mock_variant_results = {
            "SKU-1": [{"gmc_offer_id": "shopify_us_123_456"}],
            "SKU-2": [{"gmc_offer_id": "shopify_us_123_457"}],
        }

        call_count = [0]

        def select(columns):
            select_mock = MagicMock()

            def eq(column, value):
                eq_result = MagicMock()
                eq_result.data = mock_variant_results.get(value, [])
                exec_mock = MagicMock()
                exec_mock.execute.return_value = eq_result
                return exec_mock

            select_mock.eq = eq
            return select_mock

        def update(data):
            update_mock = MagicMock()

            def eq(column, value):
                exec_mock = MagicMock()
                exec_mock.execute.return_value = MagicMock()
                return exec_mock

            update_mock.eq = eq
            return update_mock

        mock_supabase.table.return_value.select = select
        mock_supabase.table.return_value.update = update

        # Call worker with 2 SKUs (should call GMC API only once)
        results = await collect_custom_labels_batch(["SKU-1", "SKU-2"])

        # Assert: fetch_merchant_center_items called exactly ONCE for the entire batch
        mock_fetch_gmc.assert_called_once()

        # Assert: Returns results for both SKUs
        assert len(results) == 2

        # Assert: Both SKUs got variants_updated
        for result in results:
            assert result["status"] == "ok"
            assert result["variants_updated"] == 1


@pytest.mark.asyncio
async def test_collect_custom_labels_batch_missing_in_gmc():
    """Test custom labels worker handles SKUs not in GMC gracefully."""
    from feedops.jobs.workers import collect_custom_labels_batch
    import feedops.jobs.workers as workers_module

    # Clear module-level cache before test
    workers_module._gmc_cache = None
    workers_module._gmc_cache_time = None

    with patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.merchant_center.fetch_merchant_center_items") as mock_fetch_gmc:

        # Setup mock Supabase client
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Mock fetch_merchant_center_items to return items WITHOUT the SKU's offer_id
        mock_fetch_gmc.return_value = [
            {
                "offerId": "shopify_US_999_999",  # Different offer ID (normalized to shopify_us_999_999)
                "customLabel0": "category:other",
            }
        ]

        # Mock variant_index query to return offer_id for SKU-1 (shopify_us_123_456 won't match)
        mock_variant_result = MagicMock()
        mock_variant_result.data = [{"gmc_offer_id": "shopify_us_123_456"}]

        select_mock = MagicMock()
        eq_mock = MagicMock()
        eq_mock.execute.return_value = mock_variant_result
        select_mock.eq.return_value = eq_mock
        mock_supabase.table.return_value.select.return_value = select_mock

        # Call worker
        results = await collect_custom_labels_batch(["SKU-1"])

        # Assert: Returns result with status "no_data" (not an error)
        assert len(results) == 1
        assert results[0]["item_id"] == "SKU-1"
        assert results[0]["status"] == "no_data"


@pytest.mark.asyncio
async def test_collect_custom_labels_batch_empty_batch():
    """Test custom labels worker handles empty batch without API calls."""
    from feedops.jobs.workers import collect_custom_labels_batch

    with patch("feedops.integrations.merchant_center.fetch_merchant_center_items") as mock_fetch_gmc:

        # Call worker with empty batch
        results = await collect_custom_labels_batch([])

        # Assert: Returns empty list
        assert results == []

        # Assert: fetch_merchant_center_items NOT called (optimization)
        mock_fetch_gmc.assert_not_called()


# =============================================================================
# General Pattern Tests
# =============================================================================


@pytest.mark.asyncio
async def test_all_workers_return_correct_shape():
    """Test all 4 workers return list[dict] with item_id and status keys."""
    from feedops.jobs.workers import (
        collect_search_terms_batch,
        collect_performance_batch,
        collect_keyword_planner_batch,
        collect_custom_labels_batch,
    )

    # Mock all dependencies
    with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockSTClient, \
         patch("feedops.integrations.google_ads_search_terms.KeywordPlannerClient") as MockKPClient, \
         patch("feedops.db.supabase_client.get_client") as mock_get_client, \
         patch("feedops.integrations.google_ads_performance.fetch_batch_product_performance") as mock_fetch_perf, \
         patch("feedops.integrations.merchant_center.fetch_merchant_center_items") as mock_fetch_gmc, \
         patch("feedops.api.backfill.compute_date_range") as mock_compute_date:

        mock_compute_date.return_value = ("2025-08-01", "2026-01-28")

        # Setup minimal mocks for each worker
        mock_supabase = MagicMock()
        mock_get_client.return_value = mock_supabase

        # Search terms mock
        mock_st_instance = MagicMock()
        MockSTClient.return_value = mock_st_instance
        mock_st_instance.fetch_search_terms.return_value = []

        # Keyword planner mock
        mock_kp_instance = MagicMock()
        MockKPClient.return_value = mock_kp_instance
        mock_kp_instance.get_historical_metrics.return_value = []

        # Performance mock
        mock_variant_result = MagicMock()
        mock_variant_result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_variant_result

        # GMC mock
        mock_fetch_gmc.return_value = []

        # Test each worker
        workers = [
            (collect_search_terms_batch, "search_terms"),
            (collect_performance_batch, "performance"),
            (collect_keyword_planner_batch, "keyword_planner"),
            (collect_custom_labels_batch, "custom_labels"),
        ]

        for worker_fn, worker_name in workers:
            results = await worker_fn(["SKU-1"])

            # Assert: Returns list[dict]
            assert isinstance(results, list), f"{worker_name} should return list"
            assert len(results) > 0, f"{worker_name} should return non-empty list"

            # Assert: Each dict has at minimum item_id and status keys
            for result in results:
                assert isinstance(result, dict), f"{worker_name} should return list of dicts"
                assert "item_id" in result, f"{worker_name} result missing item_id"
                assert "status" in result, f"{worker_name} result missing status"


@pytest.mark.asyncio
async def test_all_workers_handle_empty_batch():
    """Test all 4 workers handle empty batch without errors or API calls."""
    from feedops.jobs.workers import (
        collect_search_terms_batch,
        collect_performance_batch,
        collect_keyword_planner_batch,
        collect_custom_labels_batch,
    )

    # Mock all dependencies
    with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockSTClient, \
         patch("feedops.integrations.google_ads_search_terms.KeywordPlannerClient") as MockKPClient, \
         patch("feedops.integrations.google_ads_performance.fetch_batch_product_performance") as mock_fetch_perf, \
         patch("feedops.integrations.merchant_center.fetch_merchant_center_items") as mock_fetch_gmc:

        mock_st_instance = MagicMock()
        MockSTClient.return_value = mock_st_instance

        mock_kp_instance = MagicMock()
        MockKPClient.return_value = mock_kp_instance

        # Test each worker with empty batch
        workers = [
            (collect_search_terms_batch, "search_terms"),
            (collect_performance_batch, "performance"),
            (collect_keyword_planner_batch, "keyword_planner"),
            (collect_custom_labels_batch, "custom_labels"),
        ]

        for worker_fn, worker_name in workers:
            results = await worker_fn([])

            # Assert: Returns empty list without errors
            assert results == [], f"{worker_name} should return empty list for empty batch"

        # Assert: No API calls made for empty batches
        mock_st_instance.fetch_search_terms.assert_not_called()
        mock_kp_instance.get_historical_metrics.assert_not_called()
        mock_fetch_perf.assert_not_called()
        mock_fetch_gmc.assert_not_called()
