#!/usr/bin/env python3
"""Discover bidding, attribution, and competitive metrics from Google Ads API.

This script queries:
- DISC-07: Bidding strategies and bid data
- DISC-08: Attribution models and conversion data
- DISC-09: Competitive metrics (impression share, position, auction insights)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException


def load_client() -> GoogleAdsClient:
    """Load Google Ads API client from environment or config file."""
    try:
        return GoogleAdsClient.load_from_env()
    except Exception:
        return GoogleAdsClient.load_from_storage()


def execute_query(client: GoogleAdsClient, customer_id: str, query: str, name: str) -> dict[str, Any]:
    """Execute a GAQL query and return structured results.

    Returns:
        Dict with 'success', 'error', 'row_count', 'sample_data' keys
    """
    ga_service = client.get_service("GoogleAdsService")

    try:
        print(f"\n{name}:")
        print("-" * 80)

        response = ga_service.search_stream(customer_id=customer_id, query=query)

        rows_data = []
        for batch in response:
            for row in batch.results:
                # Convert protobuf to dict-like structure
                row_dict = {}

                # Extract all fields from the row
                for field_name in dir(row):
                    if not field_name.startswith('_'):
                        try:
                            value = getattr(row, field_name)
                            # Skip methods and special attributes
                            if not callable(value) and field_name not in ['DESCRIPTOR', 'Extensions']:
                                row_dict[field_name] = str(value)
                        except Exception:
                            continue

                rows_data.append(row_dict)

        print(f"✓ Success: {len(rows_data)} rows")
        if rows_data:
            print(f"Sample: {json.dumps(rows_data[0], indent=2)}")

        return {
            "success": True,
            "row_count": len(rows_data),
            "sample_data": rows_data[:5] if rows_data else [],
            "query": query.strip()
        }

    except GoogleAdsException as ex:
        error_msg = f"Request failed: {ex.failure.errors[0].message}"
        print(f"✗ Failed: {error_msg}")

        return {
            "success": False,
            "error": error_msg,
            "error_code": ex.failure.errors[0].error_code.name if hasattr(ex.failure.errors[0].error_code, 'name') else 'UNKNOWN',
            "query": query.strip()
        }
    except Exception as ex:
        error_msg = str(ex)
        print(f"✗ Failed: {error_msg}")

        return {
            "success": False,
            "error": error_msg,
            "query": query.strip()
        }


def discover_bidding(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover bidding strategies and bid data (DISC-07)."""
    print("\n" + "="*80)
    print("DISC-07: BIDDING DATA DISCOVERY")
    print("="*80)

    results = {}

    # Query 1: Bidding strategies
    query = """
    SELECT
      bidding_strategy.id,
      bidding_strategy.name,
      bidding_strategy.type,
      bidding_strategy.status,
      bidding_strategy.target_cpa.target_cpa_micros,
      bidding_strategy.target_roas.target_roas,
      bidding_strategy.maximize_conversions.target_cpa_micros,
      bidding_strategy.maximize_conversion_value.target_roas
    FROM bidding_strategy
    LIMIT 20
    """
    results['bidding_strategies'] = execute_query(client, customer_id, query, "1. Bidding Strategies")

    # Query 2: Campaign-level bid settings
    query = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.advertising_channel_type,
      campaign.bidding_strategy_type,
      campaign.target_cpa.target_cpa_micros,
      campaign.maximize_conversion_value.target_roas,
      campaign.manual_cpc.enhanced_cpc_enabled
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
    LIMIT 20
    """
    results['campaign_bid_settings'] = execute_query(client, customer_id, query, "2. Campaign-Level Bid Settings")

    # Query 3: Ad group bids (Standard Shopping only)
    query = """
    SELECT
      ad_group.id,
      ad_group.name,
      ad_group.cpc_bid_micros,
      ad_group.target_cpa_micros,
      ad_group.effective_target_cpa_micros,
      campaign.advertising_channel_type
    FROM ad_group
    WHERE campaign.advertising_channel_type = 'SHOPPING'
    LIMIT 20
    """
    results['ad_group_bids'] = execute_query(client, customer_id, query, "3. Ad Group Bids (Standard Shopping)")

    return results


def discover_attribution(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover attribution models and conversion data (DISC-08)."""
    print("\n" + "="*80)
    print("DISC-08: ATTRIBUTION DATA DISCOVERY")
    print("="*80)

    results = {}

    # Query 1: Conversion action settings
    query = """
    SELECT
      conversion_action.id,
      conversion_action.name,
      conversion_action.type,
      conversion_action.category,
      conversion_action.status,
      conversion_action.attribution_model_settings.attribution_model,
      conversion_action.attribution_model_settings.data_driven_model_status,
      conversion_action.click_through_lookback_window_days,
      conversion_action.view_through_lookback_window_days,
      conversion_action.counting_type
    FROM conversion_action
    WHERE conversion_action.status = 'ENABLED'
    LIMIT 20
    """
    results['conversion_action_settings'] = execute_query(client, customer_id, query, "1. Conversion Action Settings")

    # Query 2: Conversion lag distribution
    query = """
    SELECT
      segments.conversion_lag_bucket,
      metrics.conversions,
      metrics.conversions_value
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
      AND metrics.conversions > 0
    """
    results['conversion_lag_distribution'] = execute_query(client, customer_id, query, "2. Conversion Lag Distribution")

    # Query 3: Cross-device and view-through attribution
    query = """
    SELECT
      campaign.id,
      metrics.conversions,
      metrics.cross_device_conversions,
      metrics.view_through_conversions,
      metrics.all_conversions
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    """
    results['cross_device_attribution'] = execute_query(client, customer_id, query, "3. Cross-Device and View-Through Attribution")

    return results


def discover_competitive(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover competitive metrics (DISC-09)."""
    print("\n" + "="*80)
    print("DISC-09: COMPETITIVE METRICS DISCOVERY")
    print("="*80)

    results = {}

    # Query 1: Own-account impression share metrics
    query = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.advertising_channel_type,
      metrics.search_impression_share,
      metrics.search_click_share,
      metrics.search_budget_lost_impression_share,
      metrics.search_rank_lost_impression_share,
      metrics.search_top_impression_share,
      metrics.search_absolute_top_impression_share
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    LIMIT 20
    """
    results['impression_share_metrics'] = execute_query(client, customer_id, query, "1. Own-Account Impression Share Metrics")

    # Query 2: Position metrics
    query = """
    SELECT
      campaign.id,
      metrics.top_impression_percentage,
      metrics.absolute_top_impression_percentage,
      metrics.impressions,
      metrics.clicks
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    LIMIT 10
    """
    results['position_metrics'] = execute_query(client, customer_id, query, "2. Position Metrics")

    # Query 3: Auction insights (may fail - that's expected)
    query = """
    SELECT
      segments.auction_insight_domain,
      metrics.auction_insight_search_impression_share,
      metrics.auction_insight_search_overlap_rate,
      metrics.auction_insight_search_outranking_share
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    LIMIT 10
    """
    results['auction_insights'] = execute_query(client, customer_id, query, "3. Auction Insights (may be restricted)")

    # Query 4: Product-level impression share (test if available)
    query = """
    SELECT
      segments.product_item_id,
      metrics.impressions,
      metrics.search_impression_share,
      metrics.search_click_share
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 10
    ORDER BY metrics.impressions DESC
    LIMIT 10
    """
    results['product_level_impression_share'] = execute_query(client, customer_id, query, "4. Product-Level Impression Share (test)")

    return results


def main():
    """Run all discovery queries and write results to JSON."""
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print("\n" + "="*80)
    print(f"BIDDING, ATTRIBUTION, AND COMPETITIVE METRICS DISCOVERY")
    print(f"Customer ID: {customer_id}")
    print("="*80)

    client = load_client()

    # Run all discovery queries
    all_results = {
        "customer_id": customer_id,
        "bidding": discover_bidding(client, customer_id),
        "attribution": discover_attribution(client, customer_id),
        "competitive_metrics": discover_competitive(client, customer_id)
    }

    # Write to JSON file
    output_path = Path(__file__).parent.parent / ".planning" / "phases" / "02-comprehensive-data-discovery" / "disc-07-08-09-results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "="*80)
    print(f"✓ Results written to: {output_path}")
    print("="*80)

    # Print summary
    print("\nSUMMARY:")
    print("-" * 80)

    bidding_success = sum(1 for v in all_results['bidding'].values() if v.get('success', False))
    print(f"Bidding queries: {bidding_success}/{len(all_results['bidding'])} succeeded")

    attribution_success = sum(1 for v in all_results['attribution'].values() if v.get('success', False))
    print(f"Attribution queries: {attribution_success}/{len(all_results['attribution'])} succeeded")

    competitive_success = sum(1 for v in all_results['competitive_metrics'].values() if v.get('success', False))
    print(f"Competitive queries: {competitive_success}/{len(all_results['competitive_metrics'])} succeeded")

    print("\nKey Findings:")
    print("-" * 80)

    # Bidding strategies
    if all_results['bidding']['bidding_strategies'].get('success'):
        count = all_results['bidding']['bidding_strategies']['row_count']
        print(f"✓ Bidding strategies: {count} found")

    # Campaign bid settings
    if all_results['bidding']['campaign_bid_settings'].get('success'):
        count = all_results['bidding']['campaign_bid_settings']['row_count']
        print(f"✓ Campaign bid settings: {count} campaigns")

    # Conversion actions
    if all_results['attribution']['conversion_action_settings'].get('success'):
        count = all_results['attribution']['conversion_action_settings']['row_count']
        print(f"✓ Conversion actions: {count} enabled")

    # Impression share
    if all_results['competitive_metrics']['impression_share_metrics'].get('success'):
        count = all_results['competitive_metrics']['impression_share_metrics']['row_count']
        print(f"✓ Impression share data: {count} campaigns")

    # Product-level impression share
    if all_results['competitive_metrics']['product_level_impression_share'].get('success'):
        count = all_results['competitive_metrics']['product_level_impression_share']['row_count']
        if count > 0:
            print(f"✓ Product-level impression share: AVAILABLE ({count} products)")
        else:
            print("⚠ Product-level impression share: NOT AVAILABLE (zero results)")
    else:
        print("✗ Product-level impression share: NOT AVAILABLE (query failed)")

    # Auction insights
    if all_results['competitive_metrics']['auction_insights'].get('success'):
        count = all_results['competitive_metrics']['auction_insights']['row_count']
        if count > 0:
            print(f"✓ Auction insights: AVAILABLE ({count} competitors)")
        else:
            print("⚠ Auction insights: NOT AVAILABLE (zero results - likely restricted)")
    else:
        error = all_results['competitive_metrics']['auction_insights'].get('error', 'Unknown error')
        print(f"✗ Auction insights: NOT AVAILABLE ({error})")


if __name__ == "__main__":
    main()
