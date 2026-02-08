#!/usr/bin/env python3
"""Query Google Merchant Center for offer IDs to investigate sync issues."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from feedops.integrations.merchant_center import fetch_merchant_center_products


def query_gmc_product_view(product_id_pattern: str):
    """Query GMC for offer IDs matching a pattern.

    Args:
        product_id_pattern: Shopify product ID to search for (e.g., "4539975336068")
    """
    # Get merchant ID from environment
    merchant_id = os.environ.get("GMC_MERCHANT_ID")
    if not merchant_id:
        print("Error: GMC_MERCHANT_ID environment variable not set")
        sys.exit(1)

    print(f"Fetching all products from GMC (merchant ID: {merchant_id})...")
    print(f"Will filter for pattern: shopify_US_{product_id_pattern}_*\n")

    try:
        # Fetch all products using existing function
        products = fetch_merchant_center_products(limit=None, env=os.environ)
        print(f"Fetched {len(products)} total products from GMC")

        # Filter for our product pattern
        pattern_prefix = f"shopify_US_{product_id_pattern}_"
        results = []

        for product in products:
            offer_id = product.get("offerId", "")

            if offer_id.startswith(pattern_prefix):
                # Extract price from product attributes
                attributes = product.get("productAttributes", {}) or {}
                price_obj = attributes.get("price", {})
                price_str = None
                if price_obj:
                    amount = price_obj.get("amountMicros")
                    currency = price_obj.get("currencyCode")
                    if amount and currency:
                        price_str = f"{float(amount) / 1_000_000:.2f} {currency}"

                results.append({
                    "offer_id": offer_id,
                    "id": product.get("name", "").split("/")[-1] if product.get("name") else "",
                    "title": attributes.get("title", ""),
                    "price": price_str,
                    "availability": attributes.get("availability", ""),
                })

        # Print results
        if not results:
            print(f"\n❌ No products found for product ID pattern: shopify_US_{product_id_pattern}_*")
        else:
            print(f"\n✓ Found {len(results)} variant(s) in GMC:\n")
            for item in results:
                print(f"  Offer ID: {item['offer_id']}")
                print(f"  Title: {item['title'][:80]}...")
                if item['price']:
                    print(f"  Price: {item['price']}")
                if item['availability']:
                    print(f"  Availability: {item['availability']}")
                print()

        return results

    except Exception as e:
        print(f"Error querying GMC: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Default to the product we're investigating
    product_id = sys.argv[1] if len(sys.argv) > 1 else "4539975336068"

    results = query_gmc_product_view(product_id)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    if results:
        variant_ids = [r["offer_id"].split("_")[-1] for r in results]
        print(f"Product ID: {product_id}")
        print(f"Variant IDs in GMC: {', '.join(variant_ids)}")

        # Check if the Google Ads variant ID is present
        google_ads_variant = "32103134298244"
        if google_ads_variant in variant_ids:
            print(f"\n✓ Google Ads variant ID {google_ads_variant} EXISTS in GMC")
        else:
            print(f"\n✗ Google Ads variant ID {google_ads_variant} NOT FOUND in GMC")
            print(f"  GMC has different variant IDs than Google Ads reported")
