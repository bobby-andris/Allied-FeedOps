#!/usr/bin/env python3
"""Discover all Google Ads API views, metrics, and report types for Shopping campaigns.

This script comprehensively enumerates:
- DISC-01: All Shopping-relevant views/resources with field counts
- DISC-02: All performance metrics available in shopping_performance_view
- DISC-06: Report type mapping with granularity and use cases

Outputs a JSON file with live API validation results.
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


def load_client() -> GoogleAdsClient:
    """Load Google Ads API client from environment or config file."""
    try:
        return GoogleAdsClient.load_from_env()
    except Exception:
        return GoogleAdsClient.load_from_storage()


def discover_shopping_views(client: GoogleAdsClient) -> dict[str, Any]:
    """Discover all Shopping-relevant views and resources (DISC-01)."""
    print("\n" + "="*80)
    print("PART A: Discovering Shopping-relevant Views/Resources (DISC-01)")
    print("="*80)

    field_service = client.get_service("GoogleAdsFieldService")
    views = {}

    # Query 1: All shopping resources
    print("\n1. Querying shopping resources...")
    query = """
    SELECT name, category, selectable, filterable, sortable, data_type
    WHERE name LIKE 'shopping%'
    """
    response = field_service.search_google_ads_fields(query=query)

    for field in response:
        if field.category.name == "RESOURCE":
            resource_name = field.name
            if resource_name not in views:
                views[resource_name] = {
                    "category": field.category.name,
                    "selectable": field.selectable,
                    "fields": []
                }
                print(f"  Found resource: {resource_name}")

    # Query 2: All view resources
    print("\n2. Querying view resources...")
    query = """
    SELECT name, category
    WHERE name LIKE '%_view'
    """
    response = field_service.search_google_ads_fields(query=query)

    for field in response:
        if field.category.name == "RESOURCE":
            resource_name = field.name
            # Only include Shopping-relevant views
            if any(keyword in resource_name for keyword in [
                'shopping', 'product', 'search_term', 'campaign',
                'ad_group', 'performance_max', 'asset_group'
            ]):
                if resource_name not in views:
                    views[resource_name] = {
                        "category": field.category.name,
                        "selectable": True,
                        "fields": []
                    }
                    print(f"  Found view: {resource_name}")

    # Query 3: Asset group resources (PMax)
    print("\n3. Querying Performance Max resources...")
    query = """
    SELECT name, category
    WHERE name LIKE 'asset_group%'
    """
    response = field_service.search_google_ads_fields(query=query)

    for field in response:
        if field.category.name == "RESOURCE":
            resource_name = field.name
            if resource_name not in views:
                views[resource_name] = {
                    "category": field.category.name,
                    "selectable": True,
                    "fields": []
                }
                print(f"  Found PMax resource: {resource_name}")

    # Query 4: Core campaign resources
    print("\n4. Querying core campaign resources...")
    core_resources = ['campaign', 'ad_group', 'search_term_view', 'product_group_view']
    for resource in core_resources:
        query = f"""
        SELECT name, category, selectable
        WHERE name = '{resource}'
        """
        response = field_service.search_google_ads_fields(query=query)

        for field in response:
            if field.category.name == "RESOURCE":
                resource_name = field.name
                if resource_name not in views:
                    views[resource_name] = {
                        "category": field.category.name,
                        "selectable": field.selectable,
                        "fields": []
                    }
                    print(f"  Found core resource: {resource_name}")

    # For each resource, query its selectable fields
    print("\n5. Querying selectable fields for each resource...")
    for resource_name in views.keys():
        query = f"""
        SELECT name, data_type, is_repeated, selectable, filterable, sortable
        WHERE selectable_with CONTAINS ALL ('{resource_name}')
        """
        response = field_service.search_google_ads_fields(query=query)

        field_count = 0
        for field in response:
            views[resource_name]["fields"].append({
                "name": field.name,
                "data_type": field.data_type.name,
                "is_repeated": field.is_repeated,
                "selectable": field.selectable,
                "filterable": field.filterable,
                "sortable": field.sortable
            })
            field_count += 1

        views[resource_name]["field_count"] = field_count
        print(f"  {resource_name}: {field_count} fields")

    print(f"\nTotal Shopping-relevant views/resources: {len(views)}")
    return views


def discover_metrics(client: GoogleAdsClient) -> dict[str, Any]:
    """Discover all performance metrics in shopping_performance_view (DISC-02)."""
    print("\n" + "="*80)
    print("PART B: Discovering Performance Metrics (DISC-02)")
    print("="*80)

    field_service = client.get_service("GoogleAdsFieldService")

    # Query all metrics available with shopping_performance_view
    print("\nQuerying metrics for shopping_performance_view...")
    query = """
    SELECT name, data_type, is_repeated
    WHERE name LIKE 'metrics.%' AND selectable_with CONTAINS ALL ('shopping_performance_view')
    """
    response = field_service.search_google_ads_fields(query=query)

    # Categorize metrics
    metrics = {
        "core_performance": [],
        "conversion": [],
        "shopping_cart": [],
        "impression_share": [],
        "cross_sell_lead": [],
        "attribution": [],
        "asset_performance": [],
        "other": []
    }

    for field in response:
        metric_info = {
            "name": field.name,
            "data_type": field.data_type.name,
            "is_repeated": field.is_repeated
        }

        metric_name = field.name.replace("metrics.", "")

        # Categorize
        if any(kw in metric_name for kw in ['impression', 'click', 'ctr', 'cost', 'cpc', 'cpm']):
            metrics["core_performance"].append(metric_info)
        elif any(kw in metric_name for kw in ['conversion', 'roas']):
            metrics["conversion"].append(metric_info)
        elif any(kw in metric_name for kw in ['order', 'cart', 'revenue', 'units_sold', 'profit', 'margin', 'cogs']):
            metrics["shopping_cart"].append(metric_info)
        elif any(kw in metric_name for kw in ['impression_share', 'click_share', 'lost']):
            metrics["impression_share"].append(metric_info)
        elif any(kw in metric_name for kw in ['cross_sell', 'lead_']):
            metrics["cross_sell_lead"].append(metric_info)
        elif any(kw in metric_name for kw in ['attribution', 'cross_device', 'view_through']):
            metrics["attribution"].append(metric_info)
        elif any(kw in metric_name for kw in ['asset_']):
            metrics["asset_performance"].append(metric_info)
        else:
            metrics["other"].append(metric_info)

    # Print summary
    total = 0
    for category, metric_list in metrics.items():
        count = len(metric_list)
        total += count
        print(f"  {category}: {count} metrics")

    print(f"\nTotal metrics available: {total}")
    return metrics


def map_report_types(views: dict[str, Any]) -> dict[str, Any]:
    """Map report types with granularity and use cases (DISC-06)."""
    print("\n" + "="*80)
    print("PART C: Mapping Report Types (DISC-06)")
    print("="*80)

    # Define report type characteristics
    report_types = {}

    for resource_name, resource_info in views.items():
        # Determine granularity based on resource name and fields
        granularity = "unknown"
        supports_product_filter = False
        use_case = ""

        if resource_name == "shopping_performance_view":
            granularity = "product + date"
            supports_product_filter = True
            use_case = "Product-level performance analysis"
        elif resource_name == "campaign":
            granularity = "campaign + date"
            supports_product_filter = False
            use_case = "Campaign-level aggregates, budget tracking"
        elif resource_name == "ad_group":
            granularity = "ad_group + date"
            supports_product_filter = False
            use_case = "Ad group performance, product group analysis"
        elif resource_name == "search_term_view":
            granularity = "query + ad_group"
            supports_product_filter = False
            use_case = "Search query analysis (requires campaign-join for products)"
        elif resource_name == "product_group_view":
            granularity = "product_partition"
            supports_product_filter = False
            use_case = "Product group tree structure analysis"
        elif resource_name == "shopping_product":
            granularity = "variant"
            supports_product_filter = True
            use_case = "Product status, issues, and metadata (NOT performance)"
        elif "asset_group" in resource_name:
            granularity = "asset_group"
            supports_product_filter = False
            use_case = f"Performance Max {resource_name.replace('_', ' ')}"
        elif "performance_max" in resource_name:
            granularity = "placement/asset"
            supports_product_filter = False
            use_case = f"Performance Max {resource_name.replace('_', ' ')}"

        report_types[resource_name] = {
            "granularity": granularity,
            "supports_product_filter": supports_product_filter,
            "use_case": use_case,
            "field_count": resource_info.get("field_count", 0)
        }

        print(f"\n  {resource_name}:")
        print(f"    Granularity: {granularity}")
        print(f"    Product filter: {supports_product_filter}")
        print(f"    Use case: {use_case}")
        print(f"    Fields: {resource_info.get('field_count', 0)}")

    print(f"\nTotal report types mapped: {len(report_types)}")
    return report_types


def validate_metric_groups(client: GoogleAdsClient, metrics: dict[str, Any]) -> dict[str, Any]:
    """Validate which metric groups return actual data (Task 2)."""
    print("\n" + "="*80)
    print("TASK 2: Validating Metric Groups Against Live API")
    print("="*80)

    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")
    ga_service = client.get_service("GoogleAdsService")

    validation_results = {}

    # Test 1: Core performance
    print("\n1. Testing core performance metrics...")
    query = """
    SELECT
      segments.product_item_id,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.cost_micros,
      metrics.average_cpc
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 0
    LIMIT 5
    """

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "product_item_id": row.segments.product_item_id,
                    "impressions": row.metrics.impressions,
                    "clicks": row.metrics.clicks,
                    "ctr": row.metrics.ctr,
                    "cost_micros": row.metrics.cost_micros,
                    "average_cpc": row.metrics.average_cpc
                })

        validation_results["core_performance"] = {
            "status": "success",
            "row_count": len(rows),
            "sample_data": rows[:3] if rows else [],
            "has_data": len(rows) > 0
        }
        print(f"  ✓ Success: {len(rows)} rows with data")
    except Exception as e:
        validation_results["core_performance"] = {
            "status": "error",
            "error": str(e),
            "has_data": False
        }
        print(f"  ✗ Error: {e}")

    # Test 2: Conversion metrics
    print("\n2. Testing conversion metrics...")
    query = """
    SELECT
      segments.product_item_id,
      metrics.conversions,
      metrics.conversions_value,
      metrics.conversions_from_interactions_rate,
      metrics.cost_per_conversion
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 0
    LIMIT 5
    """

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "product_item_id": row.segments.product_item_id,
                    "conversions": row.metrics.conversions,
                    "conversions_value": row.metrics.conversions_value,
                    "conversions_from_interactions_rate": row.metrics.conversions_from_interactions_rate,
                    "cost_per_conversion": row.metrics.cost_per_conversion
                })

        validation_results["conversion"] = {
            "status": "success",
            "row_count": len(rows),
            "sample_data": rows[:3] if rows else [],
            "has_data": len(rows) > 0
        }
        print(f"  ✓ Success: {len(rows)} rows with data")
    except Exception as e:
        validation_results["conversion"] = {
            "status": "error",
            "error": str(e),
            "has_data": False
        }
        print(f"  ✗ Error: {e}")

    # Test 3: Shopping cart data
    print("\n3. Testing shopping cart metrics...")
    query = """
    SELECT
      segments.product_item_id,
      metrics.orders,
      metrics.average_order_value_micros,
      metrics.revenue_micros,
      metrics.units_sold,
      metrics.gross_profit_micros
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 0
    LIMIT 5
    """

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "product_item_id": row.segments.product_item_id,
                    "orders": row.metrics.orders,
                    "average_order_value_micros": row.metrics.average_order_value_micros,
                    "revenue_micros": row.metrics.revenue_micros,
                    "units_sold": row.metrics.units_sold,
                    "gross_profit_micros": row.metrics.gross_profit_micros
                })

        validation_results["shopping_cart"] = {
            "status": "success",
            "row_count": len(rows),
            "sample_data": rows[:3] if rows else [],
            "has_data": len(rows) > 0
        }
        print(f"  ✓ Success: {len(rows)} rows with data")
    except Exception as e:
        validation_results["shopping_cart"] = {
            "status": "error",
            "error": str(e),
            "has_data": False
        }
        print(f"  ✗ Error: {e}")

    # Test 4: Impression share (campaign level, not product)
    print("\n4. Testing impression share metrics...")
    query = """
    SELECT
      campaign.id,
      metrics.search_impression_share,
      metrics.search_click_share,
      metrics.search_budget_lost_impression_share,
      metrics.search_rank_lost_impression_share
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_7_DAYS
    LIMIT 5
    """

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "campaign_id": row.campaign.id,
                    "search_impression_share": row.metrics.search_impression_share,
                    "search_click_share": row.metrics.search_click_share,
                    "search_budget_lost_impression_share": row.metrics.search_budget_lost_impression_share,
                    "search_rank_lost_impression_share": row.metrics.search_rank_lost_impression_share
                })

        validation_results["impression_share"] = {
            "status": "success",
            "row_count": len(rows),
            "sample_data": rows[:3] if rows else [],
            "has_data": len(rows) > 0
        }
        print(f"  ✓ Success: {len(rows)} rows with data")
    except Exception as e:
        validation_results["impression_share"] = {
            "status": "error",
            "error": str(e),
            "has_data": False
        }
        print(f"  ✗ Error: {e}")

    # Test 5: Cross-sell/lead metrics
    print("\n5. Testing cross-sell/lead metrics...")
    query = """
    SELECT
      segments.product_item_id,
      metrics.cross_sell_revenue_micros,
      metrics.cross_sell_units_sold,
      metrics.lead_revenue_micros
    FROM shopping_performance_view
    WHERE segments.date DURING LAST_7_DAYS
      AND metrics.impressions > 0
    LIMIT 5
    """

    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append({
                    "product_item_id": row.segments.product_item_id,
                    "cross_sell_revenue_micros": row.metrics.cross_sell_revenue_micros,
                    "cross_sell_units_sold": row.metrics.cross_sell_units_sold,
                    "lead_revenue_micros": row.metrics.lead_revenue_micros
                })

        validation_results["cross_sell_lead"] = {
            "status": "success",
            "row_count": len(rows),
            "sample_data": rows[:3] if rows else [],
            "has_data": len(rows) > 0
        }
        print(f"  ✓ Success: {len(rows)} rows with data")
    except Exception as e:
        validation_results["cross_sell_lead"] = {
            "status": "error",
            "error": str(e),
            "has_data": False
        }
        print(f"  ✗ Error: {e}")

    return validation_results


def main():
    """Main execution."""
    print("\n" + "="*80)
    print("Google Ads API Shopping Data Discovery")
    print("DISC-01: Views/Resources | DISC-02: Metrics | DISC-06: Report Types")
    print("="*80)

    # Load client
    client = load_client()

    # Part A: Discover views
    views = discover_shopping_views(client)

    # Part B: Discover metrics
    metrics = discover_metrics(client)

    # Part C: Map report types
    report_types = map_report_types(views)

    # Task 2: Validate metric groups
    metric_validation = validate_metric_groups(client, metrics)

    # Combine results
    results = {
        "discovery_date": "2026-02-12",
        "customer_id": os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786"),
        "views": views,
        "metrics": metrics,
        "report_types": report_types,
        "metric_validation": metric_validation
    }

    # Write to JSON file
    output_path = Path(__file__).parent.parent / ".planning" / "phases" / "02-comprehensive-data-discovery" / "disc-01-02-06-results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*80)
    print(f"Results written to: {output_path}")
    print("="*80)
    print(f"\nSummary:")
    print(f"  Views/Resources: {len(views)}")
    print(f"  Total Metrics: {sum(len(v) for v in metrics.values())}")
    print(f"  Report Types: {len(report_types)}")
    print(f"  Metric Groups Validated: {len(metric_validation)}")


if __name__ == "__main__":
    main()
