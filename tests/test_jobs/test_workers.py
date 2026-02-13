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
