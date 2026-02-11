#!/usr/bin/env python3
"""Test Google Ads API query boundaries for Phase 1 validation.

Tests:
- API-03: Query LIMIT values (10K, 50K, 100K)
- API-04: Data retention (how far back does data exist)
- API-05: Custom label availability
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.ads.googleads.client import GoogleAdsClient
from google.protobuf.json_format import MessageToDict


def load_client() -> GoogleAdsClient:
    """Load Google Ads API client from environment or config file."""
    try:
        # Try environment variables first (Cloud Run, CI/CD)
        return GoogleAdsClient.load_from_env()
    except Exception:
        # Fall back to yaml file for local development
        return GoogleAdsClient.load_from_storage()


def run_query(client: GoogleAdsClient, customer_id: str, query: str) -> tuple[list[dict], float, str | None]:
    """Run a query and return results, response time, and any error."""
    ga_service = client.get_service("GoogleAdsService")

    start_time = datetime.now()
    error_msg = None
    results = []

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                results.append(MessageToDict(row._pb, preserving_proto_field_name=True))
    except Exception as e:
        error_msg = str(e)

    elapsed = (datetime.now() - start_time).total_seconds()
    return results, elapsed, error_msg


def test_limit_values(client: GoogleAdsClient, customer_id: str):
    """Test different LIMIT values to find maximum reliable query size (API-03)."""
    print("\n" + "="*80)
    print("API-03: Testing Query LIMIT Values")
    print("="*80 + "\n")

    limit_values = [10000, 50000, 100000]

    for limit in limit_values:
        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_30_DAYS
          AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT {limit}
        """

        print(f"Testing LIMIT {limit:,}...")
        results, elapsed, error = run_query(client, customer_id, query)

        if error:
            print(f"  ❌ FAILED: {error}")
        else:
            print(f"  ✅ SUCCESS: Returned {len(results):,} rows in {elapsed:.2f}s")
        print()


def test_data_retention(client: GoogleAdsClient, customer_id: str):
    """Test how far back data exists for this account (API-04)."""
    print("\n" + "="*80)
    print("API-04: Testing Data Retention")
    print("="*80 + "\n")

    # Test progressively older date ranges
    date_ranges = [
        ("2015-01-01", "2015-01-31", "11 years ago"),
        ("2018-01-01", "2018-01-31", "8 years ago"),
        ("2020-01-01", "2020-01-31", "6 years ago"),
        ("2023-01-01", "2023-01-31", "3 years ago"),
        ("2025-01-01", "2025-01-31", "1 year ago"),
    ]

    earliest_date_found = None

    for start_date, end_date, description in date_ranges:
        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND metrics.impressions > 0
        LIMIT 5
        """

        print(f"Testing {description} ({start_date} to {end_date})...")
        results, elapsed, error = run_query(client, customer_id, query)

        if error:
            print(f"  ❌ ERROR: {error}")
        elif len(results) > 0:
            # Find earliest date in results
            dates = [r.get("segments", {}).get("date") for r in results if r.get("segments", {}).get("date")]
            if dates:
                min_date = min(dates)
                print(f"  ✅ DATA FOUND: {len(results)} rows (earliest: {min_date})")
                if earliest_date_found is None or min_date < earliest_date_found:
                    earliest_date_found = min_date
            else:
                print(f"  ⚠️  {len(results)} rows returned but no dates")
        else:
            print(f"  ❌ NO DATA: No rows returned")
        print()

    if earliest_date_found:
        print(f"📅 Earliest date found: {earliest_date_found}")
    else:
        print("⚠️  No historical data found in any tested range")


def test_custom_labels(client: GoogleAdsClient, customer_id: str):
    """Test custom label availability (API-05)."""
    print("\n" + "="*80)
    print("API-05: Testing Custom Label Availability")
    print("="*80 + "\n")

    # Test 1: Query custom labels from shopping_performance_view
    print("Test 1: Query custom labels from shopping_performance_view")
    query1 = """
    SELECT
      segments.product_item_id,
      segments.product_custom_attribute0,
      segments.product_custom_attribute1,
      segments.product_custom_attribute2,
      metrics.impressions
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_30_DAYS
      AND metrics.impressions > 0
    ORDER BY metrics.impressions DESC
    LIMIT 20
    """

    # Initialize variables
    custom_0_populated = 0
    custom_1_populated = 0
    custom_2_populated = 0
    custom_0_values = set()

    results, elapsed, error = run_query(client, customer_id, query1)

    if error:
        print(f"  ❌ FAILED: {error}")
    else:
        print(f"  ✅ SUCCESS: Returned {len(results)} rows in {elapsed:.2f}s")

        # Analyze custom label population

        for row in results:
            segments = row.get("segments", {})
            c0 = segments.get("product_custom_attribute0")
            c1 = segments.get("product_custom_attribute1")
            c2 = segments.get("product_custom_attribute2")

            if c0:
                custom_0_populated += 1
                custom_0_values.add(c0)
            if c1:
                custom_1_populated += 1
            if c2:
                custom_2_populated += 1

        print(f"\n  Custom Attribute Population:")
        print(f"    - custom_attribute_0: {custom_0_populated}/{len(results)} products")
        print(f"    - custom_attribute_1: {custom_1_populated}/{len(results)} products")
        print(f"    - custom_attribute_2: {custom_2_populated}/{len(results)} products")

        if custom_0_values:
            print(f"\n  Sample custom_attribute_0 values:")
            for value in sorted(custom_0_values)[:10]:
                print(f"    - {value}")

    print()

    # Test 2: Try filtering by custom label (if populated)
    if custom_0_populated > 0 and custom_0_values:
        print("Test 2: Testing custom label filtering")
        sample_value = sorted(custom_0_values)[0]
        query2 = f"""
        SELECT
          segments.product_item_id,
          segments.product_custom_attribute0,
          metrics.impressions
        FROM shopping_performance_view
        WHERE segments.product_custom_attribute0 = '{sample_value}'
          AND segments.date DURING LAST_30_DAYS
          AND metrics.impressions > 0
        LIMIT 10
        """

        print(f"  Filtering by custom_attribute0 = '{sample_value}'...")
        results, elapsed, error = run_query(client, customer_id, query2)

        if error:
            print(f"  ❌ FAILED: {error}")
        else:
            print(f"  ✅ SUCCESS: Filtering works! Returned {len(results)} rows in {elapsed:.2f}s")


def main():
    """Run all API boundary tests."""
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print("="*80)
    print("Google Ads API Boundary Testing")
    print("="*80)
    print(f"Customer ID: {customer_id}")
    print(f"Date: {datetime.now().isoformat()}")

    try:
        client = load_client()
        print("✅ Google Ads client loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load Google Ads client: {e}")
        sys.exit(1)

    # Run all tests
    test_limit_values(client, customer_id)
    test_data_retention(client, customer_id)
    test_custom_labels(client, customer_id)

    print("\n" + "="*80)
    print("Testing Complete")
    print("="*80)


if __name__ == "__main__":
    main()
