#!/usr/bin/env python3
"""Find products that have recent performance data"""

import os
import sys
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

def find_active_products():
    """Find products with recent impressions"""
    client = _load_client()
    customer_id = "6253381786"

    query = """
    SELECT
      segments.product_item_id,
      metrics.impressions,
      metrics.clicks
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 10
    ORDER BY metrics.impressions DESC
    LIMIT 10
    """

    print("Finding products with recent activity...")
    print(f"Query:\n{query}\n")

    ga_service = client.get_service("GoogleAdsService")
    stream = ga_service.search_stream(customer_id=customer_id, query=query)

    products = []
    for batch in stream:
        for row in batch.results:
            row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
            products.append(row_dict)

    print(f"Found {len(products)} active products:\n")
    product_ids = []
    for i, product in enumerate(products, 1):
        product_id = product.get("segments", {}).get("product_item_id", "unknown")
        impressions = product.get("metrics", {}).get("impressions", 0)
        clicks = product.get("metrics", {}).get("clicks", 0)
        print(f"{i}. {product_id}")
        print(f"   Impressions: {impressions}, Clicks: {clicks}\n")
        product_ids.append(product_id)

    return product_ids

if __name__ == "__main__":
    product_ids = find_active_products()
    print(f"\nTop 5 product IDs for testing:")
    for pid in product_ids[:5]:
        print(f"  {pid}")
