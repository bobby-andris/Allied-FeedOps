#!/usr/bin/env python3
"""Test case sensitivity for product_item_id in shopping_performance_view"""

import os
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf.json_format import MessageToDict

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

def test_with_case(product_id: str, label: str):
    """Test query with specific case"""
    client = _load_client()
    customer_id = "6253381786"

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      metrics.impressions,
      metrics.clicks
    FROM shopping_performance_view
    WHERE segments.product_item_id = '{product_id}'
      AND segments.date DURING LAST_7_DAYS
    LIMIT 10
    """

    print(f"\n{label}: {product_id}")
    print(f"Query: WHERE segments.product_item_id = '{product_id}'")

    try:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        results = []
        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                results.append(row_dict)

        if results:
            print(f"✅ SUCCESS: {len(results)} results")
            first_result = results[0]
            returned_id = first_result.get("segments", {}).get("product_item_id", "N/A")
            print(f"   Returned product_item_id: {returned_id}")
            metrics = first_result.get("metrics", {})
            print(f"   Impressions: {metrics.get('impressions')}, Clicks: {metrics.get('clicks')}")
        else:
            print(f"❌ No results (query succeeded but returned empty)")

        return len(results) > 0

    except Exception as ex:
        print(f"❌ ERROR: {str(ex)}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("Testing case sensitivity for product_item_id filtering")
    print("=" * 80)

    # Test product that we know has activity
    base_id = "4538703609988_32096241320068"

    print("\nTesting three formats:")
    uppercase_found = test_with_case(f"shopify_US_{base_id}", "Test 1: Uppercase US")
    lowercase_found = test_with_case(f"shopify_us_{base_id}", "Test 2: Lowercase us")

    print("\n" + "=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if uppercase_found and not lowercase_found:
        print("✅ Uppercase format (shopify_US_) works")
    elif lowercase_found and not uppercase_found:
        print("✅ Lowercase format (shopify_us_) works")
    elif uppercase_found and lowercase_found:
        print("✅ Both formats work (case-insensitive)")
    else:
        print("❌ Neither format returned results (may be data issue, not case issue)")
