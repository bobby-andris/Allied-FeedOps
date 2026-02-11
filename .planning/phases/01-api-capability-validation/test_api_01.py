#!/usr/bin/env python3
"""
Test API-01: search_term_view product filtering capability
Tests whether search_term_view supports filtering by segments.product_item_id
"""

import os
import sys
import json
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

def _load_client():
    """Load Google Ads API client with proper configuration."""
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if all([developer_token, client_id, client_secret, refresh_token]):
        config = {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }
        if login_customer_id:
            config["login_customer_id"] = login_customer_id
        return GoogleAdsClient.load_from_dict(config)
    else:
        raise ValueError("Missing required Google Ads API credentials in environment")

def test_search_term_product_filter():
    """Test 1: Attempt to filter search_term_view by product_item_id (expected to fail)"""

    # Initialize client
    client = _load_client()
    customer_id = "6253381786"

    query = """
    SELECT
      search_term_view.search_term,
      campaign.id,
      metrics.impressions,
      metrics.clicks
    FROM search_term_view
    WHERE segments.product_item_id = 'shopify_US_7721863643362_42804912849122'
      AND segments.date DURING LAST_30_DAYS
    """

    print("=" * 80)
    print("TEST 1: Attempting to filter search_term_view by product_item_id")
    print("=" * 80)
    print(f"Query:\n{query}\n")

    try:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in stream:
            for row in batch.results:
                results.append({
                    "search_term": row.search_term_view.search_term,
                    "campaign_id": row.campaign.id,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks
                })

        print(f"✅ SUCCESS: Query returned {len(results)} results")
        print(f"Sample results: {json.dumps(results[:5], indent=2)}")
        return {"success": True, "results": results, "error": None}

    except GoogleAdsException as ex:
        print(f"❌ EXPECTED FAILURE: Query failed with error")
        error_details = {
            "error_code": ex.error.code().name,
            "message": ex.failure.errors[0].message if ex.failure.errors else str(ex),
            "trigger": ex.failure.errors[0].trigger.string_value if ex.failure.errors else None
        }
        print(f"Error details: {json.dumps(error_details, indent=2)}")
        return {"success": False, "results": None, "error": error_details}
    except Exception as ex:
        print(f"❌ UNEXPECTED ERROR: {str(ex)}")
        return {"success": False, "results": None, "error": str(ex)}


def test_search_term_basic():
    """Test 2: Basic search_term_view query without product filtering (expected to succeed)"""

    # Initialize client
    client = _load_client()
    customer_id = "6253381786"

    query = """
    SELECT
      search_term_view.search_term,
      campaign.id,
      metrics.impressions,
      metrics.clicks
    FROM search_term_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 10
    ORDER BY metrics.impressions DESC
    LIMIT 10
    """

    print("\n" + "=" * 80)
    print("TEST 2: Basic search_term_view query (no product filtering)")
    print("=" * 80)
    print(f"Query:\n{query}\n")

    try:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in stream:
            for row in batch.results:
                results.append({
                    "search_term": row.search_term_view.search_term,
                    "campaign_id": row.campaign.id,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks
                })

        print(f"✅ SUCCESS: Query returned {len(results)} results")
        print(f"Sample results:")
        for i, result in enumerate(results[:5], 1):
            print(f"  {i}. '{result['search_term']}' - {result['impressions']} impressions, {result['clicks']} clicks")

        return {"success": True, "results": results, "error": None}

    except GoogleAdsException as ex:
        print(f"❌ UNEXPECTED FAILURE: Query should work but failed")
        error_details = {
            "error_code": ex.error.code().name,
            "message": ex.failure.errors[0].message if ex.failure.errors else str(ex),
        }
        print(f"Error details: {json.dumps(error_details, indent=2)}")
        return {"success": False, "results": None, "error": error_details}
    except Exception as ex:
        print(f"❌ UNEXPECTED ERROR: {str(ex)}")
        return {"success": False, "results": None, "error": str(ex)}


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("API-01 TEST SUITE: search_term_view Product Filtering Capability")
    print("=" * 80)
    print()

    # Run tests
    test1_result = test_search_term_product_filter()
    test2_result = test_search_term_basic()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Product Filter): {'FAILED (expected)' if not test1_result['success'] else 'PASSED (unexpected)'}")
    print(f"Test 2 (Basic Query): {'PASSED (expected)' if test2_result['success'] else 'FAILED (unexpected)'}")

    # Conclusion
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if not test1_result['success'] and test2_result['success']:
        print("✅ API-01 CONFIRMED: search_term_view does NOT support product_item_id filtering")
        print("   - Product filter query failed as expected")
        print("   - Basic query worked, confirming search_term_view is functional")
        print("   - Campaign-join pattern is required for product→search term association")
    else:
        print("⚠️  UNEXPECTED RESULTS - Further investigation needed")

    # Save results
    output_file = "/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/phases/01-api-capability-validation/api-01-test-results.json"
    with open(output_file, "w") as f:
        json.dump({
            "test_1_product_filter": test1_result,
            "test_2_basic_query": test2_result
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")
