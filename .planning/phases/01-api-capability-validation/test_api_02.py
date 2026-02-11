#!/usr/bin/env python3
"""
Test API-02: shopping_performance_view product-level query capability
Tests whether shopping_performance_view supports filtering by segments.product_item_id
"""

import os
import sys
import json
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict

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


def get_sample_product_ids(client, customer_id: str, count: int = 5) -> list[str]:
    """Get a few sample product IDs with recent activity."""
    # Return known active product IDs (lowercase format, as API returns and expects)
    return [
        "shopify_us_4538703609988_32096241320068",
        "shopify_us_8751009038562_46118169444578",
        "shopify_us_4543465947268_32123035451524",
        "shopify_us_4538765508740_32096780222596",
        "shopify_us_4542830280836_32117943369860"
    ]


def test_single_product_query():
    """Test 1: Query shopping_performance_view for a single product"""

    client = _load_client()
    customer_id = "6253381786"

    # Use an active product ID (lowercase us format, as returned by API)
    product_id = "shopify_us_4538703609988_32096241320068"

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      campaign.advertising_channel_type,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.conversions,
      metrics.conversions_value,
      metrics.cost_micros
    FROM shopping_performance_view
    WHERE segments.product_item_id = '{product_id}'
      AND segments.date DURING LAST_30_DAYS
    ORDER BY segments.date DESC
    LIMIT 30
    """

    print("=" * 80)
    print("TEST 1: Single product query on shopping_performance_view")
    print("=" * 80)
    print(f"Product ID: {product_id}")
    print(f"Query:\n{query}\n")

    try:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                results.append(row_dict)

        print(f"✅ SUCCESS: Query returned {len(results)} results")

        if results:
            # Show first 5 results
            print(f"\nSample results (first 5 rows):")
            for i, result in enumerate(results[:5], 1):
                segments = result.get("segments", {})
                metrics = result.get("metrics", {})
                campaign = result.get("campaign", {})

                date = segments.get("date", "N/A")
                impressions = int(metrics.get("impressions", 0))
                clicks = int(metrics.get("clicks", 0))
                ctr = float(metrics.get("ctr", 0))
                conversions = float(metrics.get("conversions", 0))
                cost_micros = int(metrics.get("cost_micros", 0))
                channel_type = campaign.get("advertising_channel_type", "N/A")

                print(f"  {i}. Date: {date}, Channel: {channel_type}")
                print(f"     Impressions: {impressions}, Clicks: {clicks}, CTR: {ctr:.2%}")
                print(f"     Conversions: {conversions}, Cost: ${cost_micros/1_000_000:.2f}")
        else:
            print("⚠️  Query succeeded but returned no results (product may not have recent data)")

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


def test_batch_product_query():
    """Test 2: Query shopping_performance_view for multiple products (IN clause)"""

    client = _load_client()
    customer_id = "6253381786"

    # Get sample product IDs
    product_ids = get_sample_product_ids(client, customer_id, count=5)

    # Build IN clause
    ids_clause = ", ".join(f"'{pid}'" for pid in product_ids)

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr
    FROM shopping_performance_view
    WHERE segments.product_item_id IN ({ids_clause})
      AND segments.date DURING LAST_30_DAYS
    ORDER BY segments.product_item_id, segments.date DESC
    """

    print("\n" + "=" * 80)
    print("TEST 2: Batch product query (IN clause)")
    print("=" * 80)
    print(f"Product IDs: {product_ids}")
    print(f"Query:\n{query}\n")

    try:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                results.append(row_dict)

        print(f"✅ SUCCESS: Query returned {len(results)} results")

        if results:
            # Group by product_item_id
            by_product = {}
            for result in results:
                product_id = result.get("segments", {}).get("product_item_id", "unknown")
                if product_id not in by_product:
                    by_product[product_id] = []
                by_product[product_id].append(result)

            print(f"\nResults grouped by product ({len(by_product)} products):")
            for product_id, rows in list(by_product.items())[:5]:
                print(f"\n  Product: {product_id}")
                print(f"  Rows: {len(rows)}")

                # Show first row for this product
                if rows:
                    first_row = rows[0]
                    metrics = first_row.get("metrics", {})
                    segments = first_row.get("segments", {})
                    print(f"  Sample (latest): Date={segments.get('date')}, Impressions={metrics.get('impressions')}, Clicks={metrics.get('clicks')}")
        else:
            print("⚠️  Query succeeded but returned no results (products may not have recent data)")

        return {"success": True, "results": results, "product_count": len(by_product) if results else 0, "error": None}

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
    print("API-02 TEST SUITE: shopping_performance_view Product Query Capability")
    print("=" * 80)
    print()

    # Run tests
    test1_result = test_single_product_query()
    test2_result = test_batch_product_query()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Single Product): {'PASSED' if test1_result['success'] else 'FAILED'}")
    print(f"Test 2 (Batch Query): {'PASSED' if test2_result['success'] else 'FAILED'}")

    # Conclusion
    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if test1_result['success'] and test2_result['success']:
        print("✅ API-02 CONFIRMED: shopping_performance_view fully supports product-level filtering")
        print("   - Single product query worked successfully")
        print("   - Batch query (IN clause) worked successfully")
        print("   - Product-level backfill strategy is fully supported")

        # Show metrics
        if test1_result['results']:
            print(f"\n   Test 1 returned {len(test1_result['results'])} rows for single product")
        if test2_result['results']:
            print(f"   Test 2 returned {len(test2_result['results'])} rows for {test2_result.get('product_count', 0)} products")
    else:
        print("⚠️  UNEXPECTED RESULTS - Further investigation needed")

    # Save results
    output_file = "/Users/bobby/Documents/GitHub/Allied-FeedOps/.planning/phases/01-api-capability-validation/api-02-test-results.json"
    with open(output_file, "w") as f:
        json.dump({
            "test_1_single_product": {
                "success": test1_result["success"],
                "row_count": len(test1_result["results"]) if test1_result["results"] else 0,
                "sample_results": test1_result["results"][:5] if test1_result["results"] else [],
                "error": test1_result["error"]
            },
            "test_2_batch_query": {
                "success": test2_result["success"],
                "row_count": len(test2_result["results"]) if test2_result["results"] else 0,
                "product_count": test2_result.get("product_count", 0),
                "sample_results": test2_result["results"][:5] if test2_result["results"] else [],
                "error": test2_result["error"]
            }
        }, f, indent=2)
    print(f"\nResults saved to: {output_file}")
