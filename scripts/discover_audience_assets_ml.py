#!/usr/bin/env python3
"""Discover audience segmentation, asset-level performance, and ML insights data.

Covers DISC-10 (asset performance), DISC-11 (audience segmentation), and DISC-12 (ML insights).
Tests each API capability with live queries and documents availability.
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


def safe_query(ga_service, customer_id: str, query: str, description: str) -> dict[str, Any]:
    """Execute query safely and return structured result."""
    result = {
        "description": description,
        "query": query.strip(),
        "success": False,
        "data": [],
        "error": None,
        "row_count": 0
    }

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)

        for batch in response:
            for row in batch.results:
                # Convert row to dict (simplified representation)
                row_dict = {}
                for field in str(row).split('\n'):
                    field = field.strip()
                    if field and ':' in field:
                        key, value = field.split(':', 1)
                        row_dict[key.strip()] = value.strip()
                result["data"].append(row_dict)

        result["success"] = True
        result["row_count"] = len(result["data"])

    except GoogleAdsException as ex:
        # Extract error message from failure
        error_message = str(ex)
        if hasattr(ex, 'failure') and ex.failure:
            errors = ex.failure.errors
            if errors:
                error_message = errors[0].message

        result["error"] = {
            "type": "GoogleAdsException",
            "message": error_message,
            "request_id": ex.request_id if hasattr(ex, 'request_id') else None
        }
    except Exception as ex:
        result["error"] = {
            "type": type(ex).__name__,
            "message": str(ex)
        }

    return result


def discover_audience_segmentation(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover audience segmentation capabilities (DISC-11)."""
    print("\n" + "="*80)
    print("DISC-11: Audience Segmentation Discovery")
    print("="*80)

    ga_service = client.get_service("GoogleAdsService")
    results = {}

    # 1. Device segmentation
    print("\n1. Testing device segmentation...")
    query = """
    SELECT
      segments.device,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions,
      metrics.cost_micros
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    """
    results["device_segmentation"] = safe_query(
        ga_service, customer_id, query,
        "Device-level performance segmentation for Shopping and PMax campaigns"
    )
    print(f"   Result: {'✓ SUCCESS' if results['device_segmentation']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['device_segmentation']['row_count']}")

    # 2. Day of week
    print("\n2. Testing day-of-week segmentation...")
    query = """
    SELECT
      segments.day_of_week,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    """
    results["day_of_week"] = safe_query(
        ga_service, customer_id, query,
        "Day-of-week performance patterns"
    )
    print(f"   Result: {'✓ SUCCESS' if results['day_of_week']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['day_of_week']['row_count']}")

    # 3. Hour of day
    print("\n3. Testing hour-of-day segmentation...")
    query = """
    SELECT
      segments.hour,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_7_DAYS
    """
    results["hour_of_day"] = safe_query(
        ga_service, customer_id, query,
        "Hour-of-day performance patterns"
    )
    print(f"   Result: {'✓ SUCCESS' if results['hour_of_day']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['hour_of_day']['row_count']}")

    # 4. Geographic performance
    print("\n4. Testing geographic segmentation...")
    query = """
    SELECT
      campaign.advertising_channel_type,
      geographic_view.country_criterion_id,
      geographic_view.location_type,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions
    FROM geographic_view
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    ORDER BY metrics.impressions DESC
    LIMIT 20
    """
    results["geographic_segmentation"] = safe_query(
        ga_service, customer_id, query,
        "Geographic performance by location"
    )
    print(f"   Result: {'✓ SUCCESS' if results['geographic_segmentation']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['geographic_segmentation']['row_count']}")

    # 5. Demographics (may not be available for Shopping)
    print("\n5. Testing demographics (age range)...")
    query = """
    SELECT
      ad_group.id,
      segments.adjusted_age_range,
      metrics.impressions,
      metrics.clicks
    FROM ad_group
    WHERE campaign.advertising_channel_type = 'SHOPPING'
      AND segments.date DURING LAST_30_DAYS
      AND metrics.impressions > 0
    LIMIT 20
    """
    results["demographics_age"] = safe_query(
        ga_service, customer_id, query,
        "Demographics segmentation (age range) - typically not available for Shopping"
    )
    print(f"   Result: {'✓ SUCCESS' if results['demographics_age']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['demographics_age']['row_count']}")
    if not results["demographics_age"]["success"]:
        print(f"   Note: Demographics typically not available for Shopping campaigns (Search/Display only)")

    # 6. Product-level device segmentation
    print("\n6. Testing product-level device segmentation...")
    query = """
    SELECT
      segments.product_item_id,
      segments.device,
      metrics.impressions,
      metrics.clicks
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 10
    ORDER BY metrics.impressions DESC
    LIMIT 20
    """
    results["product_device_segmentation"] = safe_query(
        ga_service, customer_id, query,
        "Product-level performance segmented by device"
    )
    print(f"   Result: {'✓ SUCCESS' if results['product_device_segmentation']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['product_device_segmentation']['row_count']}")

    return results


def discover_asset_performance(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover asset-level performance capabilities (DISC-10)."""
    print("\n" + "="*80)
    print("DISC-10: Asset-Level Performance Discovery")
    print("="*80)

    ga_service = client.get_service("GoogleAdsService")
    results = {}

    # 1. PMax asset group assets with performance labels
    print("\n1. Testing PMax asset group assets (performance labels)...")
    query = """
    SELECT
      asset_group.name,
      asset_group_asset.field_type,
      asset_group_asset.performance_label,
      asset_group_asset.status
    FROM asset_group_asset
    WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
    LIMIT 30
    """
    results["pmax_asset_performance"] = safe_query(
        ga_service, customer_id, query,
        "PMax asset performance labels (LOW/GOOD/BEST)"
    )
    print(f"   Result: {'✓ SUCCESS' if results['pmax_asset_performance']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['pmax_asset_performance']['row_count']}")

    # 2. PMax top asset combinations
    print("\n2. Testing PMax top asset combinations...")
    query = """
    SELECT
      asset_group.name,
      asset_group_top_combination_view.asset_group_top_combinations
    FROM asset_group_top_combination_view
    LIMIT 10
    """
    results["pmax_top_combinations"] = safe_query(
        ga_service, customer_id, query,
        "PMax top-performing asset combinations"
    )
    print(f"   Result: {'✓ SUCCESS' if results['pmax_top_combinations']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['pmax_top_combinations']['row_count']}")

    # 3. Asset interaction segments (test if available)
    print("\n3. Testing asset interaction segments...")
    query = """
    SELECT
      segments.asset_interaction_target.asset,
      segments.asset_interaction_target.interaction_on_this_asset,
      metrics.impressions,
      metrics.clicks
    FROM campaign
    WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
      AND segments.date DURING LAST_30_DAYS
    LIMIT 10
    """
    results["asset_interaction_segments"] = safe_query(
        ga_service, customer_id, query,
        "Asset interaction tracking (which assets users interacted with)"
    )
    print(f"   Result: {'✓ SUCCESS' if results['asset_interaction_segments']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['asset_interaction_segments']['row_count']}")

    # Note about Standard Shopping
    results["standard_shopping_note"] = {
        "description": "Standard Shopping campaigns do not have ad assets",
        "explanation": "Shopping ads are generated automatically from GMC product data (title, description, image, price). Asset-level metrics only exist for Performance Max campaigns which use asset groups with multiple headlines, descriptions, and images."
    }

    return results


def discover_ml_insights(client: GoogleAdsClient, customer_id: str) -> dict[str, Any]:
    """Discover ML insights and recommendations (DISC-12)."""
    print("\n" + "="*80)
    print("DISC-12: ML Insights and Recommendations Discovery")
    print("="*80)

    ga_service = client.get_service("GoogleAdsService")
    results = {}

    # 1. Shopping-specific recommendations (try detailed first, fall back to simple)
    print("\n1. Testing Shopping recommendations (detailed)...")
    query_detailed = """
    SELECT
      recommendation.type,
      recommendation.campaign,
      recommendation.impact.base_metrics.impressions,
      recommendation.impact.base_metrics.clicks,
      recommendation.impact.potential_metrics.impressions,
      recommendation.impact.potential_metrics.clicks
    FROM recommendation
    WHERE recommendation.type IN (
      'SHOPPING_ADD_AGE_GROUP',
      'SHOPPING_ADD_COLOR',
      'SHOPPING_ADD_GENDER',
      'SHOPPING_ADD_GTIN',
      'SHOPPING_ADD_MORE_IDENTIFIERS',
      'SHOPPING_ADD_PRODUCTS_TO_CAMPAIGN',
      'SHOPPING_ADD_SIZE',
      'SHOPPING_FIX_DISAPPROVED_PRODUCTS',
      'SHOPPING_TARGET_ALL_OFFERS',
      'SHOPPING_MIGRATE_REGULAR_SHOPPING_CAMPAIGN_OFFERS_TO_PERFORMANCE_MAX'
    )
    LIMIT 20
    """
    results["recommendations_detailed"] = safe_query(
        ga_service, customer_id, query_detailed,
        "Shopping recommendations with impact metrics"
    )
    print(f"   Result: {'✓ SUCCESS' if results['recommendations_detailed']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['recommendations_detailed']['row_count']}")

    # Fall back to simpler query if detailed fails
    if not results["recommendations_detailed"]["success"]:
        print("\n   Trying simplified recommendations query...")
        query_simple = """
        SELECT
          recommendation.type,
          recommendation.campaign,
          recommendation.dismissed
        FROM recommendation
        WHERE recommendation.type LIKE 'SHOPPING_%'
        LIMIT 20
        """
        results["recommendations_simple"] = safe_query(
            ga_service, customer_id, query_simple,
            "Shopping recommendations (simplified - no impact metrics)"
        )
        print(f"   Fallback result: {'✓ SUCCESS' if results['recommendations_simple']['success'] else '✗ FAILED'}")
        print(f"   Rows: {results['recommendations_simple']['row_count']}")

    # 2. Campaign optimization scores
    print("\n2. Testing campaign optimization scores...")
    query = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.advertising_channel_type,
      campaign.optimization_score
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND campaign.status = 'ENABLED'
    LIMIT 20
    """
    results["optimization_scores"] = safe_query(
        ga_service, customer_id, query,
        "Campaign optimization scores (0-100 scale)"
    )
    print(f"   Result: {'✓ SUCCESS' if results['optimization_scores']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['optimization_scores']['row_count']}")

    # 3. Search term insights (ML-categorized)
    print("\n3. Testing search term insights (ML categories)...")
    query = """
    SELECT
      campaign_search_term_insight.category_label,
      campaign_search_term_insight.id
    FROM campaign_search_term_insight
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
    LIMIT 20
    """
    results["search_term_insights"] = safe_query(
        ga_service, customer_id, query,
        "ML-categorized search term insights"
    )
    print(f"   Result: {'✓ SUCCESS' if results['search_term_insights']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['search_term_insights']['row_count']}")

    # 4. Change events
    print("\n4. Testing change event tracking...")
    query = """
    SELECT
      change_event.change_date_time,
      change_event.change_resource_type,
      change_event.changed_fields,
      change_event.client_type,
      change_event.user_email
    FROM change_event
    WHERE change_event.change_date_time DURING LAST_14_DAYS
    ORDER BY change_event.change_date_time DESC
    LIMIT 20
    """
    results["change_events"] = safe_query(
        ga_service, customer_id, query,
        "Campaign change event tracking (audit log)"
    )
    print(f"   Result: {'✓ SUCCESS' if results['change_events']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['change_events']['row_count']}")

    # 5. Quality score (if available for Shopping)
    print("\n5. Testing quality score data...")
    query = """
    SELECT
      ad_group_criterion.criterion_id,
      ad_group_criterion.quality_info.quality_score,
      ad_group_criterion.quality_info.creative_quality_score,
      ad_group_criterion.quality_info.landing_page_quality_score,
      ad_group_criterion.quality_info.search_predicted_ctr
    FROM ad_group_criterion
    WHERE campaign.advertising_channel_type = 'SHOPPING'
      AND ad_group_criterion.quality_info.quality_score IS NOT NULL
    LIMIT 10
    """
    results["quality_scores"] = safe_query(
        ga_service, customer_id, query,
        "Quality score data (typically for Search, not Shopping)"
    )
    print(f"   Result: {'✓ SUCCESS' if results['quality_scores']['success'] else '✗ FAILED'}")
    print(f"   Rows: {results['quality_scores']['row_count']}")
    if not results["quality_scores"]["success"]:
        print(f"   Note: Quality scores typically not available for Shopping campaigns")

    return results


def create_data_value_assessment() -> dict[str, Any]:
    """Create data value assessment ranking all discovered data sources by FeedOps relevance."""
    return {
        "assessment_criteria": "Relevance to FeedOps content optimization",
        "rating_scale": {
            "HIGH": "Directly informs content generation decisions",
            "MEDIUM": "Indirectly useful for understanding performance context",
            "LOW": "Limited content relevance but useful for campaign management",
            "NOT_AVAILABLE": "Confirmed unavailable for this account/campaign type"
        },
        "data_sources": {
            "HIGH_VALUE": [
                {
                    "source": "search_term_view",
                    "value": "HIGH",
                    "reason": "Actual search queries reveal customer language, intent, and discovery patterns",
                    "use_case": "Inform title/description word choice, identify content gaps, discover new keywords",
                    "discovery": "DISC-01, DISC-07"
                },
                {
                    "source": "shopping_performance_view (product-level metrics)",
                    "value": "HIGH",
                    "reason": "Product-level CTR/CVR directly measures content effectiveness",
                    "use_case": "Identify underperforming products needing content optimization, A/B test content changes",
                    "discovery": "DISC-02, DISC-03, DISC-05"
                },
                {
                    "source": "segments.product_custom_attribute (custom labels)",
                    "value": "HIGH",
                    "reason": "Enables efficient segmentation by category/tier for batch operations",
                    "use_case": "Filter products for optimization, analyze performance by category, prioritize high-value SKUs",
                    "discovery": "DISC-08"
                },
                {
                    "source": "campaign_search_term_insight (ML categories)",
                    "value": "HIGH",
                    "reason": "Google's ML categorization of search terms reveals themes/topics",
                    "use_case": "Discover content themes, identify topic clusters, validate category alignment",
                    "discovery": "DISC-12"
                }
            ],
            "MEDIUM_VALUE": [
                {
                    "source": "segments.device",
                    "value": "MEDIUM",
                    "reason": "Device performance differences may indicate UX issues or content length optimization",
                    "use_case": "Optimize description length for mobile, identify device-specific performance gaps",
                    "discovery": "DISC-11"
                },
                {
                    "source": "segments.hour / segments.day_of_week",
                    "value": "MEDIUM",
                    "reason": "Time-based patterns reveal customer behavior but don't directly inform content",
                    "use_case": "Understand purchase timing, identify peak shopping periods",
                    "discovery": "DISC-11"
                },
                {
                    "source": "geographic_view",
                    "value": "MEDIUM",
                    "reason": "Geographic performance may indicate regional terminology or shipping concerns",
                    "use_case": "Identify regional underperformance, validate shipping info prominence",
                    "discovery": "DISC-11"
                },
                {
                    "source": "recommendation.type (Shopping recommendations)",
                    "value": "MEDIUM",
                    "reason": "Google's recommendations identify missing product attributes",
                    "use_case": "Discover data quality issues, identify missing attributes to add to content",
                    "discovery": "DISC-12"
                },
                {
                    "source": "campaign.optimization_score",
                    "value": "MEDIUM",
                    "reason": "Overall campaign health metric, not product-specific",
                    "use_case": "Monitor overall account health, prioritize optimization efforts",
                    "discovery": "DISC-12"
                },
                {
                    "source": "asset_group_asset.performance_label (PMax only)",
                    "value": "MEDIUM",
                    "reason": "Asset performance labels (LOW/GOOD/BEST) for PMax creative testing",
                    "use_case": "Identify best-performing headlines/descriptions for PMax campaigns",
                    "discovery": "DISC-10"
                }
            ],
            "LOW_VALUE": [
                {
                    "source": "shopping_performance_view.benchmark_cpc",
                    "value": "LOW",
                    "reason": "Competitive bidding data, not content-related",
                    "use_case": "Bid strategy, competitive analysis",
                    "discovery": "DISC-06"
                },
                {
                    "source": "campaign_criterion (negative keywords)",
                    "value": "LOW",
                    "reason": "Campaign-level exclusions, not product content",
                    "use_case": "Understand filtering strategy, avoid excluded terms in content",
                    "discovery": "DISC-04"
                },
                {
                    "source": "change_event",
                    "value": "LOW",
                    "reason": "Audit log for campaign changes, not product performance",
                    "use_case": "Track who changed what and when, correlate changes with performance",
                    "discovery": "DISC-12"
                },
                {
                    "source": "metrics.absolute_top_impression_percentage",
                    "value": "LOW",
                    "reason": "Ad position metrics, driven by bid/budget not content",
                    "use_case": "Bid optimization, not content optimization",
                    "discovery": "DISC-06"
                }
            ],
            "NOT_AVAILABLE": [
                {
                    "source": "segments.adjusted_age_range / adjusted_gender",
                    "value": "NOT_AVAILABLE",
                    "reason": "Demographics not available for Shopping/PMax campaigns (Search/Display only)",
                    "discovery": "DISC-11"
                },
                {
                    "source": "ad_group_criterion.quality_info.quality_score",
                    "value": "NOT_AVAILABLE",
                    "reason": "Quality scores only for Search campaigns with keywords, not Shopping",
                    "discovery": "DISC-12"
                },
                {
                    "source": "segments.asset_interaction_target (PMax)",
                    "value": "NOT_AVAILABLE",
                    "reason": "Asset interaction tracking appears to not be populated (query succeeds but returns no data)",
                    "discovery": "DISC-10"
                },
                {
                    "source": "performance_max_placement_view (full metrics)",
                    "value": "NOT_AVAILABLE",
                    "reason": "Only impressions metric supported, not clicks/conversions",
                    "discovery": "DISC-09"
                }
            ]
        },
        "priority_recommendations": {
            "phase_3_focus": [
                "search_term_view (DISC-01, DISC-07) - Customer language and intent",
                "shopping_performance_view (DISC-02, DISC-03, DISC-05) - Content effectiveness measurement",
                "segments.product_custom_attribute (DISC-08) - Efficient product segmentation",
                "campaign_search_term_insight (DISC-12) - ML-categorized search themes"
            ],
            "secondary_testing": [
                "segments.device (DISC-11) - Device-specific content optimization",
                "recommendation.type (DISC-12) - Missing product attributes",
                "asset_group_asset.performance_label (DISC-10) - PMax creative insights"
            ],
            "deprioritize": [
                "Time-based segmentation (hour/day_of_week) - Limited content relevance",
                "Competitive/bidding metrics - Not content-related",
                "Change events - Audit only, not optimization input"
            ]
        }
    }


def main():
    """Main execution."""
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print("="*80)
    print("Google Ads API Discovery: Audience, Assets, ML Insights")
    print("="*80)
    print(f"Customer ID: {customer_id}")

    client = load_client()

    # Run all discoveries
    audience_results = discover_audience_segmentation(client, customer_id)
    asset_results = discover_asset_performance(client, customer_id)
    ml_results = discover_ml_insights(client, customer_id)
    data_value = create_data_value_assessment()

    # Combine all results
    output = {
        "customer_id": customer_id,
        "discovery_scope": "DISC-10 (Asset Performance), DISC-11 (Audience Segmentation), DISC-12 (ML Insights)",
        "audience_segmentation": audience_results,
        "asset_performance": asset_results,
        "ml_insights": ml_results,
        "data_value_assessment": data_value
    }

    # Write to JSON file
    output_path = Path(__file__).parent.parent / ".planning/phases/02-comprehensive-data-discovery/disc-10-11-12-results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*80)
    print("Discovery Complete")
    print("="*80)
    print(f"Results written to: {output_path}")
    print("\nSummary:")
    print(f"  Audience segmentation queries: {len(audience_results)}")
    print(f"  Asset performance queries: {len(asset_results)}")
    print(f"  ML insights queries: {len(ml_results)}")
    print(f"  Data value assessment: {len(data_value['data_sources'])} categories")


if __name__ == "__main__":
    main()
