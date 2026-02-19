#!/usr/bin/env python3
"""
Strategic test SKU selector for Phase 15 search terms backfill validation.

Queries Google Ads and Supabase to identify 6-8 test SKUs that cover
all important cases: high-impression, multi-variant family, published,
low-impression, and SKUs with existing synced_at data.

Usage:
    PYTHONPATH=./src .venv/bin/python scripts/select_test_skus.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

# Ensure PYTHONPATH includes src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _load_google_ads_client():
    """Load Google Ads API client from env vars or config file."""
    from google.ads.googleads.client import GoogleAdsClient

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

    config_path = os.getenv("GOOGLE_ADS_CONFIG_PATH")
    if config_path:
        return GoogleAdsClient.load_from_storage(path=config_path)

    return GoogleAdsClient.load_from_storage()


def _get_supabase_client():
    """Get Supabase client.

    Supports both Cloud Run env vars (SUPABASE_URL, SUPABASE_KEY) and
    Vercel/local env vars (NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY).
    """
    from supabase import create_client

    url = (
        os.getenv("SUPABASE_URL")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    )
    key = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )

    if not url or not key:
        raise ValueError(
            "Supabase credentials not found. Set SUPABASE_URL + SUPABASE_KEY "
            "or NEXT_PUBLIC_SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY"
        )

    return create_client(url, key)


def fetch_impressions_by_offer_id(customer_id: str, days: int = 30) -> dict[str, int]:
    """Query Google Ads shopping_performance_view for impressions per offer_id."""
    from google.protobuf.json_format import MessageToDict

    ga_client = _load_google_ads_client()
    ga_service = ga_client.get_service("GoogleAdsService")

    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")

    query = f"""
        SELECT
            segments.product_item_id,
            SUM(metrics.impressions) as metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.advertising_channel_type = 'SHOPPING'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 2000
    """

    # Note: Google Ads GAQL doesn't support SUM() in SELECT like SQL.
    # Instead we need to group by product_item_id and aggregate client-side.
    # Also: campaign.advertising_channel_type must be in SELECT when used in WHERE.
    query = f"""
        SELECT
            segments.product_item_id,
            campaign.advertising_channel_type,
            metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
            AND campaign.advertising_channel_type = 'SHOPPING'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 10000
    """

    impressions_by_offer: dict[str, int] = defaultdict(int)

    try:
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                segments = row_dict.get("segments", {}) or {}
                metrics = row_dict.get("metrics", {}) or {}
                item_id = segments.get("product_item_id")
                impressions = int(metrics.get("impressions", 0) or 0)
                if item_id:
                    impressions_by_offer[item_id] += impressions
    except Exception as e:
        print(f"ERROR fetching Google Ads data: {e}")
        sys.exit(1)

    return dict(impressions_by_offer)


def map_offer_ids_to_skus(
    supabase, offer_ids: list[str]
) -> dict[str, str]:
    """Map GMC offer IDs to master_skus via variant_index table.

    Returns: {offer_id (lowercase): master_sku}
    """
    # Normalize to lowercase for lookup
    lower_offer_ids = [oid.lower() for oid in offer_ids]

    mapping = {}
    batch_size = 500

    for i in range(0, len(lower_offer_ids), batch_size):
        batch = lower_offer_ids[i : i + batch_size]
        try:
            result = (
                supabase.table("variant_index")
                .select("gmc_offer_id, master_sku")
                .in_("gmc_offer_id", batch)
                .execute()
            )
            for row in result.data or []:
                mapping[row["gmc_offer_id"]] = row["master_sku"]
        except Exception as e:
            print(f"WARNING: Supabase batch lookup error: {e}")

    return mapping


def get_published_skus(supabase) -> set[str]:
    """Get set of master_skus that have been published."""
    try:
        result = (
            supabase.table("publish_events")
            .select("master_sku")
            .not_.is_("published_at", "null")
            .execute()
        )
        return {row["master_sku"] for row in (result.data or [])}
    except Exception as e:
        print(f"WARNING: Could not fetch published SKUs: {e}")
        return set()


def get_multi_variant_families(supabase) -> dict[str, list[str]]:
    """Get product families with 3+ master_skus sharing the same product_id.

    Returns: {product_id: [master_sku1, master_sku2, ...]}
    """
    try:
        # Use RPC or raw SQL to get families
        result = supabase.rpc(
            "execute_sql",
            {
                "query": """
                    SELECT product_id, COUNT(DISTINCT master_sku) as sku_count,
                           array_agg(DISTINCT master_sku) as skus
                    FROM variant_index
                    WHERE product_id IS NOT NULL
                    GROUP BY product_id
                    HAVING COUNT(DISTINCT master_sku) >= 3
                    ORDER BY sku_count DESC
                    LIMIT 20
                """
            },
        ).execute()
        families = {}
        for row in result.data or []:
            families[row["product_id"]] = row["skus"]
        return families
    except Exception:
        # Fallback: manual query via .select()
        try:
            result = (
                supabase.table("variant_index")
                .select("product_id, master_sku")
                .not_.is_("product_id", "null")
                .execute()
            )
            # Group by product_id client-side
            by_product: dict[str, set[str]] = defaultdict(set)
            for row in result.data or []:
                by_product[row["product_id"]].add(row["master_sku"])
            return {
                pid: list(skus)
                for pid, skus in by_product.items()
                if len(skus) >= 3
            }
        except Exception as e:
            print(f"WARNING: Could not fetch multi-variant families: {e}")
            return {}


def get_skus_with_synced_data(supabase) -> set[str]:
    """Get master_skus that already have rows with synced_at IS NOT NULL."""
    try:
        result = (
            supabase.table("search_queries")
            .select("master_sku")
            .not_.is_("synced_at", "null")
            .not_.is_("master_sku", "null")
            .limit(1000)
            .execute()
        )
        return {row["master_sku"] for row in (result.data or [])}
    except Exception as e:
        print(f"WARNING: Could not fetch SKUs with synced data: {e}")
        return set()


def main():
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print("=" * 60)
    print("Phase 15 — Strategic Test SKU Selection")
    print("=" * 60)

    # Step 1: Fetch impressions from Google Ads
    print("\n[1/5] Fetching impressions from Google Ads (last 30 days)...")
    impressions_by_offer = fetch_impressions_by_offer_id(customer_id, days=30)
    print(f"      Found {len(impressions_by_offer)} offer IDs with impressions")

    # Step 2: Connect to Supabase
    print("\n[2/5] Connecting to Supabase...")
    supabase = _get_supabase_client()

    # Step 3: Map offer IDs to master_skus
    print("\n[3/5] Mapping offer IDs to master_skus via variant_index...")
    offer_ids = list(impressions_by_offer.keys())
    offer_to_sku = map_offer_ids_to_skus(supabase, offer_ids)
    print(f"      Mapped {len(offer_to_sku)} of {len(offer_ids)} offer IDs to master_skus")

    # Build impression map by master_sku (sum across all variants)
    impressions_by_sku: dict[str, int] = defaultdict(int)
    for offer_id, impressions in impressions_by_offer.items():
        lower_offer = offer_id.lower()
        if lower_offer in offer_to_sku:
            master_sku = offer_to_sku[lower_offer]
            if master_sku:
                impressions_by_sku[master_sku] += impressions

    print(f"      Found {len(impressions_by_sku)} distinct master_skus with impressions")

    # Step 4: Get Supabase context
    print("\n[4/5] Fetching Supabase context...")
    published_skus = get_published_skus(supabase)
    multi_variant_families = get_multi_variant_families(supabase)
    skus_with_synced_data = get_skus_with_synced_data(supabase)

    # Flatten multi-variant family members into a set
    family_skus: set[str] = set()
    for skus in multi_variant_families.values():
        family_skus.update(skus)

    print(f"      Published SKUs: {len(published_skus)}")
    print(f"      Multi-variant families (3+ SKUs): {len(multi_variant_families)}")
    print(f"      SKUs already with synced_at data: {len(skus_with_synced_data)}")

    # Step 5: Categorize and select
    print("\n[5/5] Selecting strategic test SKUs...")

    # Sort by impressions descending
    sorted_skus = sorted(impressions_by_sku.items(), key=lambda x: x[1], reverse=True)

    high_impression = [(sku, imp) for sku, imp in sorted_skus if imp > 5000]
    medium_impression = [(sku, imp) for sku, imp in sorted_skus if 500 <= imp <= 5000]
    low_impression = [(sku, imp) for sku, imp in sorted_skus if 10 <= imp < 500]

    print(f"\n  Impression categories:")
    print(f"    High (>5k):      {len(high_impression)} SKUs")
    print(f"    Medium (500-5k): {len(medium_impression)} SKUs")
    print(f"    Low (10-500):    {len(low_impression)} SKUs")

    recommended = {}
    rationale = {}

    # Select 2 high-impression SKUs (prefer published)
    high_published = [(sku, imp) for sku, imp in high_impression if sku in published_skus]
    high_unpublished = [(sku, imp) for sku, imp in high_impression if sku not in published_skus]

    if high_published:
        sku, imp = high_published[0]
        recommended[sku] = imp
        rationale[sku] = f"high-impression ({imp:,}), published"

    if len(high_published) >= 2:
        sku, imp = high_published[1]
        if sku not in recommended:
            recommended[sku] = imp
            rationale[sku] = f"high-impression ({imp:,}), published"
    elif high_unpublished:
        sku, imp = high_unpublished[0]
        if sku not in recommended:
            recommended[sku] = imp
            rationale[sku] = f"high-impression ({imp:,}), not yet published"

    # Ensure we have at least 2 high-impression SKUs
    if len([s for s in recommended if impressions_by_sku.get(s, 0) > 5000]) < 2:
        for sku, imp in high_impression:
            if sku not in recommended:
                recommended[sku] = imp
                rationale[sku] = f"high-impression ({imp:,})"
                break

    # Select 2 medium-impression SKUs (prefer multi-variant family member)
    medium_family = [(sku, imp) for sku, imp in medium_impression if sku in family_skus]
    medium_other = [(sku, imp) for sku, imp in medium_impression if sku not in family_skus]

    if medium_family:
        sku, imp = medium_family[0]
        if sku not in recommended:
            # Find the family this SKU belongs to
            family_info = ""
            for pid, members in multi_variant_families.items():
                if sku in members:
                    family_info = f", family of {len(members)} SKUs ({', '.join(members[:3])}...)"
                    break
            recommended[sku] = imp
            rationale[sku] = f"medium-impression ({imp:,}), multi-variant family{family_info}"

    if medium_other:
        sku, imp = medium_other[0]
        if sku not in recommended:
            recommended[sku] = imp
            rationale[sku] = f"medium-impression ({imp:,})"

    # If no medium found, try to get a second family member
    if len(recommended) < 4 and medium_family:
        for sku, imp in medium_family[1:]:
            if sku not in recommended:
                recommended[sku] = imp
                rationale[sku] = f"medium-impression ({imp:,}), multi-variant family member"
                break

    # Select 1 low-impression SKU
    if low_impression:
        sku, imp = low_impression[0]
        if sku not in recommended:
            recommended[sku] = imp
            rationale[sku] = f"low-impression ({imp:,}), edge case test"

    # Select 1 SKU that already has synced_at rows (idempotency test)
    for sku in skus_with_synced_data:
        if sku not in recommended and sku in impressions_by_sku:
            imp = impressions_by_sku[sku]
            recommended[sku] = imp
            rationale[sku] = f"impression ({imp:,}), already has synced_at data — idempotency test"
            break

    # Build final output
    recommended_skus = list(recommended.keys())

    output = {
        "recommended_skus": recommended_skus,
        "rationale": rationale,
        "stats": {
            "total_skus_with_impressions": len(impressions_by_sku),
            "high_impression_count": len(high_impression),
            "medium_impression_count": len(medium_impression),
            "low_impression_count": len(low_impression),
            "published_sku_count": len(published_skus),
            "multi_variant_family_count": len(multi_variant_families),
            "skus_with_synced_data_count": len(skus_with_synced_data),
        },
    }

    # Print formatted summary
    print("\n" + "=" * 60)
    print("RECOMMENDED TEST SKUs")
    print("=" * 60)
    for i, sku in enumerate(recommended_skus, 1):
        print(f"\n  {i}. {sku}")
        print(f"     {rationale.get(sku, 'no rationale')}")

    print("\n" + "=" * 60)
    print("JSON OUTPUT (use recommended_skus for Task 3 curl)")
    print("=" * 60)
    print(json.dumps(output, indent=2))

    return output


if __name__ == "__main__":
    main()
