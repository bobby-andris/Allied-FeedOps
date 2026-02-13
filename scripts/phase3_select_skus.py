#!/usr/bin/env python3
"""
Phase 3 Sample Testing & Analysis - SKU Selection and Search Term Fetching

This script performs:
- SAMP-01: Select 5-10 representative test SKUs across product categories
- SAMP-02: Fetch Google Ads search terms for selected SKUs

Outputs:
- .planning/phases/03-sample-testing-analysis/sample-skus.json
- .planning/phases/03-sample-testing-analysis/search-terms-by-sku.json
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.ads.googleads.client import GoogleAdsClient
from google.protobuf.json_format import MessageToDict
from feedops.db.supabase_client import get_client as get_supabase_client


def get_google_ads_client():
    """Create Google Ads API client from environment variables."""
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if not all([developer_token, client_id, client_secret, refresh_token]):
        raise ValueError("Google Ads credentials not found in environment")

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


def select_test_skus(supabase, google_ads_client, customer_id: str = "6253381786"):
    """
    SAMP-01: Select 5-10 representative test SKUs across product categories.

    Strategy:
    1. Query product_catalog for SKUs across target categories
    2. Map to variant_index to get gmc_offer_ids
    3. Validate activity via Google Ads shopping_performance_view
    4. Select 1-2 active SKUs per category

    Returns:
        List of dicts with master_sku, category, gmc_offer_id, title, impressions_30d
    """
    print("\n=== SAMP-01: SKU Selection ===\n")

    # Target categories for diverse sampling
    target_categories = [
        "towel bar",
        "grab bar",
        "mirror",
        "shelf",
        "robe hook"
    ]

    candidate_skus = []

    # Get candidates from each category
    for category in target_categories:
        print(f"Searching category: {category}")

        try:
            result = supabase.table("product_catalog").select(
                "master_sku, gmc_id, title, category"
            ).ilike("category", f"%{category}%").limit(5).execute()

            if result.data:
                print(f"  Found {len(result.data)} candidates")
                for row in result.data:
                    # Map to variant_index to get actual gmc_offer_id
                    variant_result = supabase.table("variant_index").select(
                        "gmc_offer_id"
                    ).eq("master_sku", row["master_sku"]).limit(1).execute()

                    if variant_result.data:
                        gmc_offer_id = variant_result.data[0]["gmc_offer_id"]
                        candidate_skus.append({
                            "master_sku": row["master_sku"],
                            "category": category,
                            "gmc_offer_id": gmc_offer_id,
                            "title": row["title"]
                        })
            else:
                print(f"  No products found for category: {category}")

        except Exception as e:
            print(f"  Error querying category {category}: {e}")

    print(f"\nFound {len(candidate_skus)} candidate SKUs across categories")

    # Validate activity via Google Ads API
    print("\nValidating activity via Google Ads API...")

    ga_service = google_ads_client.get_service("GoogleAdsService")
    active_skus = []

    # Build offer ID list for validation query (lowercase for API)
    offer_ids = [sku["gmc_offer_id"] for sku in candidate_skus]

    if not offer_ids:
        print("No candidate SKUs to validate. Using fallback known-active SKUs.")
        # Use known-active offer IDs from Phase 1
        fallback_offer_ids = [
            "shopify_us_4538703609988_32096241320068",
            "shopify_us_8751009038562_46118169444578",
            "shopify_us_4543465947268_32123035451524",
            "shopify_us_4538765508740_32096780222596",
            "shopify_us_4542830280836_32117943369860"
        ]

        for offer_id in fallback_offer_ids:
            # Map back to master_sku
            variant_result = supabase.table("variant_index").select(
                "master_sku, finish"
            ).eq("gmc_offer_id", offer_id).limit(1).execute()

            if variant_result.data:
                master_sku = variant_result.data[0]["master_sku"]

                # Get product info
                product_result = supabase.table("product_catalog").select(
                    "title, category"
                ).eq("master_sku", master_sku).limit(1).execute()

                if product_result.data:
                    candidate_skus.append({
                        "master_sku": master_sku,
                        "category": product_result.data[0].get("category", "unknown"),
                        "gmc_offer_id": offer_id,
                        "title": product_result.data[0]["title"]
                    })

        offer_ids = fallback_offer_ids

    # Query Google Ads for activity (use lowercase offer IDs)
    in_clause = ','.join([f"'{offer_id}'" for offer_id in offer_ids])

    query = f"""
        SELECT
            segments.product_item_id,
            campaign.advertising_channel_type,
            metrics.impressions
        FROM shopping_performance_view
        WHERE segments.product_item_id IN ({in_clause})
          AND segments.date DURING LAST_30_DAYS
          AND campaign.advertising_channel_type = 'SHOPPING'
    """

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        # Aggregate impressions by offer_id
        impressions_by_offer = {}

        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                segments = row_dict.get("segments", {}) or {}
                metrics = row_dict.get("metrics", {}) or {}

                offer_id = segments.get("product_item_id")
                impressions = int(metrics.get("impressions", 0) or 0)

                if offer_id:
                    impressions_by_offer[offer_id] = impressions_by_offer.get(offer_id, 0) + impressions

        print(f"Found activity data for {len(impressions_by_offer)} products")

        # Filter candidates to those with activity
        for candidate in candidate_skus:
            impressions = impressions_by_offer.get(candidate["gmc_offer_id"], 0)
            if impressions > 0:
                candidate["impressions_30d"] = impressions
                active_skus.append(candidate)

        print(f"Filtered to {len(active_skus)} SKUs with confirmed activity")

        # Select 1-2 per category, prioritize by impressions
        selected_skus = []
        category_counts = {}

        # Sort by impressions descending
        active_skus.sort(key=lambda x: x.get("impressions_30d", 0), reverse=True)

        for sku in active_skus:
            category = sku["category"]

            # Take up to 2 per category
            if category_counts.get(category, 0) < 2:
                selected_skus.append(sku)
                category_counts[category] = category_counts.get(category, 0) + 1

            # Stop at 10 SKUs
            if len(selected_skus) >= 10:
                break

        print(f"\nSelected {len(selected_skus)} SKUs across {len(set(s['category'] for s in selected_skus))} categories")

        # If we have fewer than 5 SKUs, supplement with fallback known-active SKUs
        if len(selected_skus) < 5:
            print(f"\nNeed more SKUs (have {len(selected_skus)}, target 5-10). Adding fallback known-active SKUs...")

            fallback_offer_ids = [
                "shopify_us_4538703609988_32096241320068",
                "shopify_us_8751009038562_46118169444578",
                "shopify_us_4543465947268_32123035451524",
                "shopify_us_4538765508740_32096780222596",
                "shopify_us_4542830280836_32117943369860"
            ]

            # Only add fallbacks that aren't already in selected_skus
            selected_offer_ids = {s["gmc_offer_id"] for s in selected_skus}

            for offer_id in fallback_offer_ids:
                if offer_id in selected_offer_ids:
                    continue

                # Map to master_sku
                variant_result = supabase.table("variant_index").select(
                    "master_sku"
                ).eq("gmc_offer_id", offer_id).limit(1).execute()

                if variant_result.data:
                    master_sku = variant_result.data[0]["master_sku"]

                    # Get product info
                    product_result = supabase.table("product_catalog").select(
                        "title, category"
                    ).eq("master_sku", master_sku).limit(1).execute()

                    if product_result.data:
                        # Get impressions for this SKU if available
                        impressions = impressions_by_offer.get(offer_id, 0)

                        selected_skus.append({
                            "master_sku": master_sku,
                            "category": product_result.data[0].get("category", "unknown"),
                            "gmc_offer_id": offer_id,
                            "title": product_result.data[0]["title"],
                            "impressions_30d": impressions
                        })

                        print(f"  Added fallback: {master_sku} ({product_result.data[0].get('category', 'unknown')})")

                        if len(selected_skus) >= 8:
                            break

            print(f"\nFinal selection: {len(selected_skus)} SKUs across {len(set(s['category'] for s in selected_skus))} categories")

        return selected_skus

    except Exception as e:
        print(f"Error validating activity: {e}")
        # Return top 8 candidates without activity validation
        return candidate_skus[:8]


def fetch_search_terms_for_sku(supabase, google_ads_client, master_sku: str, customer_id: str = "6253381786", days: int = 90):
    """
    SAMP-02: Fetch search terms for a single master SKU using campaign-join pattern.

    Strategy:
    1. Get all variant offer_ids for the master_sku from variant_index
    2. Query shopping_performance_view to find campaigns with these products
    3. Query search_term_view for those campaigns
    4. Aggregate and deduplicate search terms

    Returns:
        Dict with variant_count, search_term_count, total_impressions, terms list
    """
    # Get all variants for this master_sku
    variant_result = supabase.table("variant_index").select(
        "gmc_offer_id"
    ).eq("master_sku", master_sku).execute()

    if not variant_result.data:
        return {
            "variant_count": 0,
            "search_term_count": 0,
            "total_impressions": 0,
            "terms": []
        }

    offer_ids = [v["gmc_offer_id"] for v in variant_result.data]
    variant_count = len(offer_ids)

    ga_service = google_ads_client.get_service("GoogleAdsService")

    # Step 1: Find campaigns where these products appear
    in_clause = ','.join([f"'{offer_id}'" for offer_id in offer_ids])

    # Calculate date range (LAST_N_DAYS syntax doesn't work, need explicit dates)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    campaign_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            segments.product_item_id
        FROM shopping_performance_view
        WHERE segments.product_item_id IN ({in_clause})
          AND segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
          AND campaign.advertising_channel_type = 'SHOPPING'
          AND metrics.impressions > 0
    """

    campaign_ids = set()

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=campaign_query)

        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                campaign = row_dict.get("campaign", {}) or {}
                campaign_id = str(campaign.get("id", ""))
                if campaign_id:
                    campaign_ids.add(campaign_id)

    except Exception as e:
        print(f"    Error fetching campaigns for {master_sku}: {e}")
        return {
            "variant_count": variant_count,
            "search_term_count": 0,
            "total_impressions": 0,
            "terms": []
        }

    if not campaign_ids:
        return {
            "variant_count": variant_count,
            "search_term_count": 0,
            "total_impressions": 0,
            "terms": []
        }

    # Step 2: Fetch search terms for these campaigns
    campaign_in_clause = ','.join([f"'{cid}'" for cid in campaign_ids])

    search_term_query = f"""
        SELECT
            search_term_view.search_term,
            campaign.advertising_channel_type,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions
        FROM search_term_view
        WHERE campaign.id IN ({campaign_in_clause})
          AND segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
          AND campaign.advertising_channel_type = 'SHOPPING'
    """

    # Aggregate search terms
    terms_dict = {}

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=search_term_query)

        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)

                search_term = row_dict.get("search_term_view", {}).get("search_term")
                metrics = row_dict.get("metrics", {}) or {}

                if not search_term:
                    continue

                impressions = int(metrics.get("impressions", 0) or 0)
                clicks = int(metrics.get("clicks", 0) or 0)
                conversions = float(metrics.get("conversions", 0) or 0)

                # Deduplicate by search term
                if search_term not in terms_dict:
                    terms_dict[search_term] = {
                        "search_term": search_term,
                        "impressions": 0,
                        "clicks": 0,
                        "conversions": 0
                    }

                terms_dict[search_term]["impressions"] += impressions
                terms_dict[search_term]["clicks"] += clicks
                terms_dict[search_term]["conversions"] += conversions

    except Exception as e:
        print(f"    Error fetching search terms for {master_sku}: {e}")

    # Convert to list and sort by impressions
    terms_list = sorted(terms_dict.values(), key=lambda x: x["impressions"], reverse=True)

    total_impressions = sum(t["impressions"] for t in terms_list)

    return {
        "variant_count": variant_count,
        "search_term_count": len(terms_list),
        "total_impressions": total_impressions,
        "terms": terms_list
    }


def main():
    """Main execution function."""
    print("Phase 3 Sample Testing & Analysis")
    print("=" * 60)

    # Initialize clients
    print("\nInitializing clients...")
    try:
        supabase = get_supabase_client()
    except Exception as e:
        print(f"ERROR: Failed to initialize Supabase client: {e}")
        print("\nMake sure environment variables are set. Run:")
        print("  source .venv/bin/activate")
        print("  set -a && source .env.vercel && set +a")
        print("  python scripts/phase3_select_skus.py")
        sys.exit(1)

    google_ads_client = get_google_ads_client()
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print(f"Customer ID: {customer_id}")

    # SAMP-01: Select test SKUs
    selected_skus = select_test_skus(supabase, google_ads_client, customer_id)

    if not selected_skus:
        print("\nERROR: No SKUs selected. Exiting.")
        sys.exit(1)

    # Save sample SKUs
    output_dir = os.path.join(os.path.dirname(__file__), "..", ".planning", "phases", "03-sample-testing-analysis")
    os.makedirs(output_dir, exist_ok=True)

    sample_skus_path = os.path.join(output_dir, "sample-skus.json")

    with open(sample_skus_path, "w") as f:
        json.dump(selected_skus, f, indent=2)

    print(f"\nSaved {len(selected_skus)} selected SKUs to: {sample_skus_path}")

    # SAMP-02: Fetch search terms for each SKU
    print("\n=== SAMP-02: Search Term Fetching ===\n")

    search_terms_by_sku = {
        "metadata": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "lookback_days": 90,
            "sku_count": len(selected_skus)
        },
        "skus": {}
    }

    for i, sku_data in enumerate(selected_skus):
        master_sku = sku_data["master_sku"]
        print(f"[{i+1}/{len(selected_skus)}] Fetching search terms for {master_sku}...")

        search_data = fetch_search_terms_for_sku(supabase, google_ads_client, master_sku, customer_id, days=90)

        search_terms_by_sku["skus"][master_sku] = search_data

        print(f"    Variants: {search_data['variant_count']}, Search terms: {search_data['search_term_count']}, Impressions: {search_data['total_impressions']:,}")

        # Rate limit protection: 1 second delay between SKUs
        if i < len(selected_skus) - 1:
            time.sleep(1)

    # Save search terms
    search_terms_path = os.path.join(output_dir, "search-terms-by-sku.json")

    with open(search_terms_path, "w") as f:
        json.dump(search_terms_by_sku, f, indent=2)

    print(f"\nSaved search terms to: {search_terms_path}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nSKUs selected: {len(selected_skus)}")
    print(f"Categories covered: {len(set(s['category'] for s in selected_skus))}")

    total_search_terms = sum(data["search_term_count"] for data in search_terms_by_sku["skus"].values())
    total_impressions = sum(data["total_impressions"] for data in search_terms_by_sku["skus"].values())

    print(f"Total unique search terms: {total_search_terms}")
    print(f"Total impressions: {total_impressions:,}")

    # Category breakdown
    print("\nCategory breakdown:")
    category_counts = {}
    for sku in selected_skus:
        cat = sku["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count} SKUs")

    print("\nPhase 3 sample selection complete!")


if __name__ == "__main__":
    main()
