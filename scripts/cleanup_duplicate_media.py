#!/usr/bin/env python3
"""
One-time cleanup script to remove duplicate Shopify media.
Run with: python cleanup_duplicate_media.py
"""

import os
import sys
from supabase import create_client
import requests
from typing import List, Dict, Any
from collections import defaultdict

# Get credentials from environment
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_ACCESS_TOKEN")

if not all([SUPABASE_URL, SUPABASE_KEY, SHOPIFY_STORE_URL, SHOPIFY_ACCESS_TOKEN]):
    print("❌ Missing required environment variables:")
    print("   - SUPABASE_URL")
    print("   - SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")
    print("   - SHOPIFY_STORE_URL")
    print("   - SHOPIFY_ACCESS_TOKEN")
    sys.exit(1)


def get_shopify_product_media(product_id: str) -> List[Dict[str, Any]]:
    """Get all media for a Shopify product."""
    query = """
    query getProductMedia($id: ID!) {
      product(id: $id) {
        id
        media(first: 100) {
          edges {
            node {
              ... on MediaImage {
                id
                alt
                status
                image {
                  url
                }
              }
            }
          }
        }
      }
    }
    """

    response = requests.post(
        f"https://{SHOPIFY_STORE_URL}/admin/api/2026-01/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        },
        json={
            "query": query,
            "variables": {"id": f"gid://shopify/Product/{product_id}"},
        },
    )

    data = response.json()
    media = []

    if data.get("data", {}).get("product", {}).get("media"):
        for edge in data["data"]["product"]["media"]["edges"]:
            media.append(edge["node"])

    return media


def delete_shopify_media(product_id: str, media_ids: List[str]) -> Dict[str, Any]:
    """Delete media from Shopify product."""
    mutation = """
    mutation deleteMedia($productId: ID!, $mediaIds: [ID!]!) {
      productDeleteMedia(productId: $productId, mediaIds: $mediaIds) {
        deletedMediaIds
        deletedProductImageIds
        mediaUserErrors {
          field
          message
        }
      }
    }
    """

    response = requests.post(
        f"https://{SHOPIFY_STORE_URL}/admin/api/2026-01/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        },
        json={
            "query": mutation,
            "variables": {
                "productId": f"gid://shopify/Product/{product_id}",
                "mediaIds": media_ids,
            },
        },
    )

    return response.json()


def cleanup_duplicates():
    """Find and remove duplicate Shopify media records for FT-16 only."""
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    TARGET_SKU = "FT-16"

    print(f"🔍 Finding products with lifestyle images for {TARGET_SKU}...")

    # Get unique products that have lifestyle images migrated for FT-16 only
    response = (
        supabase.table("variant_lifestyle_images")
        .select("gmc_offer_id, master_sku, finish")
        .eq("master_sku", TARGET_SKU)
        .neq("shopify_cdn_url", None)
        .execute()
    )

    if not response.data:
        print(f"✓ No migrated images found for {TARGET_SKU}")
        return

    # Get unique product IDs
    unique_offers = {img["gmc_offer_id"]: img for img in response.data}

    print(f"📦 Checking {len(unique_offers)} products for duplicate media...")

    total_duplicates_removed = 0

    for gmc_offer_id, img_info in unique_offers.items():
        # Get Shopify product ID
        variant_response = (
            supabase.table("variant_index")
            .select("shopify_product_id")
            .eq("gmc_offer_id", gmc_offer_id)
            .single()
            .execute()
        )

        if not variant_response.data or not variant_response.data.get("shopify_product_id"):
            continue

        product_id = variant_response.data["shopify_product_id"]

        # Get all media for this product from Shopify
        media = get_shopify_product_media(product_id)

        if not media:
            continue

        # Group media by alt text
        media_by_alt = defaultdict(list)
        for m in media:
            alt = m.get("alt") or "no-alt"
            media_by_alt[alt].append(m)

        # Find duplicate media (same alt text, multiple records)
        # SAFETY: Only consider media that matches our lifestyle image pattern "FT-16 - {finish}"
        duplicates = {}
        for alt, items in media_by_alt.items():
            if len(items) > 1 and alt and "FT-16 -" in alt:
                duplicates[alt] = items

        if not duplicates:
            continue

        print(f"\n  Product {img_info['master_sku']} ({product_id}):")

        for alt, items in duplicates.items():
            print(f"    Alt text: '{alt}' - {len(items)} copies (WILL DELETE {len(items)-1})")

            # Keep the first one (arbitrary choice), delete the rest
            to_keep = items[0]
            to_delete = items[1:]

            print(f"      ✓ Keeping: {to_keep['id']}")
            print(f"      🗑️  Deleting {len(to_delete)} duplicates...")

            media_ids_to_delete = [m["id"] for m in to_delete]

            try:
                result = delete_shopify_media(product_id, media_ids_to_delete)

                if result.get("data", {}).get("productDeleteMedia", {}).get("mediaUserErrors"):
                    errors = result["data"]["productDeleteMedia"]["mediaUserErrors"]
                    print(f"      ❌ Shopify errors: {errors}")
                else:
                    deleted_count = len(result.get("data", {}).get("productDeleteMedia", {}).get("deletedMediaIds", []))
                    print(f"      ✓ Deleted from Shopify: {deleted_count} media records")
                    total_duplicates_removed += deleted_count
            except Exception as e:
                print(f"      ❌ Failed to delete from Shopify: {e}")

    print(f"\n✅ Cleanup complete! Removed {total_duplicates_removed} duplicate media records from Shopify.")


if __name__ == "__main__":
    cleanup_duplicates()
