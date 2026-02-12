#!/usr/bin/env python3
"""Discover custom label filtering capabilities and Performance Max data patterns.

Tests:
- DISC-03: Custom label filtering (exact, IN, NOT, cross-attribute)
- DISC-04: Custom label population strategy
- DISC-05: Performance Max campaign data patterns
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from google.ads.googleads.client import GoogleAdsClient


def load_client() -> GoogleAdsClient:
    """Load Google Ads API client from environment or config file."""
    try:
        return GoogleAdsClient.load_from_env()
    except Exception:
        return GoogleAdsClient.load_from_storage()


def execute_query(ga_service, customer_id: str, query: str, label: str):
    """Execute a GAQL query and return results with timing."""
    start = time.time()
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            for row in batch.results:
                rows.append(row)
        elapsed = time.time() - start
        return {
            "success": True,
            "label": label,
            "row_count": len(rows),
            "elapsed_seconds": round(elapsed, 3),
            "query": query.strip(),
            "sample_data": rows[:5]  # First 5 rows
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "success": False,
            "label": label,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 3),
            "query": query.strip()
        }


def discover_custom_label_values(ga_service, customer_id: str) -> dict:
    """Discover which custom attributes are populated and with what values."""
    print("\n" + "="*80)
    print("PART A: Custom Label Discovery (DISC-03)")
    print("="*80)

    results = {
        "attributes": {},
        "population_summary": {}
    }

    # Test each custom attribute 0-4
    for attr_num in range(5):
        attr_name = f"segments.product_custom_attribute{attr_num}"
        print(f"\nDiscovering values for {attr_name}...")

        query = f"""
        SELECT
          {attr_name},
          metrics.impressions
        FROM shopping_performance_view
        WHERE segments.date DURING LAST_30_DAYS
          AND metrics.impressions > 0
        LIMIT 50
        """

        result = execute_query(ga_service, customer_id, query, f"discover_attribute{attr_num}")

        if result["success"]:
            # Collect unique values
            values = defaultdict(int)
            for row in result["sample_data"]:
                val = getattr(row.segments, f"product_custom_attribute{attr_num}", "")
                if val:
                    values[val] += 1

            unique_values = list(values.keys())
            results["attributes"][f"custom_attribute{attr_num}"] = {
                "populated": len(unique_values) > 0,
                "unique_values": unique_values[:20],  # First 20 unique values
                "total_unique_in_sample": len(unique_values),
                "sample_size": result["row_count"]
            }

            print(f"  ✓ Found {len(unique_values)} unique values in sample of {result['row_count']} products")
            if unique_values:
                print(f"    Sample values: {', '.join(unique_values[:5])}")
        else:
            results["attributes"][f"custom_attribute{attr_num}"] = {
                "populated": False,
                "error": result["error"]
            }
            print(f"  ✗ Error: {result['error']}")

    return results


def test_custom_label_filtering(ga_service, customer_id: str, discovery_results: dict) -> dict:
    """Test various custom label filtering operations."""
    print("\n" + "="*80)
    print("Custom Label Filtering Tests")
    print("="*80)

    filtering_tests = []

    # Find a populated attribute with values for testing
    test_attr = None
    test_values = []
    for attr_name, attr_data in discovery_results["attributes"].items():
        if attr_data.get("populated") and attr_data.get("unique_values"):
            test_attr = attr_name.replace("custom_attribute", "")
            test_values = attr_data["unique_values"]
            break

    if not test_attr or not test_values:
        print("⚠ No populated custom attributes found - skipping filtering tests")
        return {"tests": [], "skipped": True, "reason": "No populated attributes"}

    attr_num = test_attr
    field_name = f"segments.product_custom_attribute{attr_num}"

    print(f"\nUsing custom_attribute{attr_num} for filtering tests...")
    print(f"Available values: {', '.join(test_values[:5])}\n")

    # Test 1: Exact match
    if test_values:
        test_value = test_values[0]
        print(f"Test 1: Exact match filter ({field_name} = '{test_value}')")
        query = f"""
        SELECT
          segments.product_item_id,
          {field_name},
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE {field_name} = '{test_value}'
          AND segments.date DURING LAST_30_DAYS
        LIMIT 20
        """
        result = execute_query(ga_service, customer_id, query, "exact_match")
        filtering_tests.append(result)
        print(f"  {'✓' if result['success'] else '✗'} Rows: {result.get('row_count', 0)}, Time: {result['elapsed_seconds']}s")

    # Test 2: IN clause
    if len(test_values) >= 3:
        in_values = test_values[:3]
        in_clause = "', '".join(in_values)
        print(f"\nTest 2: IN clause filter ({field_name} IN [3 values])")
        query = f"""
        SELECT
          segments.product_item_id,
          {field_name},
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE {field_name} IN ('{in_clause}')
          AND segments.date DURING LAST_30_DAYS
        LIMIT 20
        """
        result = execute_query(ga_service, customer_id, query, "in_clause")
        filtering_tests.append(result)
        print(f"  {'✓' if result['success'] else '✗'} Rows: {result.get('row_count', 0)}, Time: {result['elapsed_seconds']}s")

    # Test 3: NOT filter
    if test_values:
        test_value = test_values[0]
        print(f"\nTest 3: NOT filter ({field_name} != '{test_value}')")
        query = f"""
        SELECT
          segments.product_item_id,
          {field_name},
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE {field_name} != '{test_value}'
          AND segments.date DURING LAST_30_DAYS
        LIMIT 20
        """
        result = execute_query(ga_service, customer_id, query, "not_filter")
        filtering_tests.append(result)
        print(f"  {'✓' if result['success'] else '✗'} Rows: {result.get('row_count', 0)}, Time: {result['elapsed_seconds']}s")

    # Test 4: Cross-attribute filter (if we have multiple populated attributes)
    populated_attrs = [
        (name.replace("custom_attribute", ""), data["unique_values"][0])
        for name, data in discovery_results["attributes"].items()
        if data.get("populated") and data.get("unique_values")
    ]

    if len(populated_attrs) >= 2:
        attr1_num, attr1_val = populated_attrs[0]
        attr2_num, attr2_val = populated_attrs[1]
        print(f"\nTest 4: Cross-attribute filter (attribute{attr1_num} AND attribute{attr2_num})")
        query = f"""
        SELECT
          segments.product_item_id,
          segments.product_custom_attribute{attr1_num},
          segments.product_custom_attribute{attr2_num},
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE segments.product_custom_attribute{attr1_num} = '{attr1_val}'
          AND segments.product_custom_attribute{attr2_num} = '{attr2_val}'
          AND segments.date DURING LAST_30_DAYS
        LIMIT 20
        """
        result = execute_query(ga_service, customer_id, query, "cross_attribute")
        filtering_tests.append(result)
        print(f"  {'✓' if result['success'] else '✗'} Rows: {result.get('row_count', 0)}, Time: {result['elapsed_seconds']}s")
    else:
        print("\nTest 4: Cross-attribute filter - SKIPPED (only one populated attribute)")

    return {"tests": filtering_tests, "skipped": False}


def analyze_population_strategy(discovery_results: dict) -> dict:
    """Analyze custom label population strategy (DISC-04)."""
    print("\n" + "="*80)
    print("PART B: Custom Label Population Strategy (DISC-04)")
    print("="*80)

    analysis = {
        "currently_populated": [],
        "available_slots": [],
        "recommendations": []
    }

    for attr_name, attr_data in discovery_results["attributes"].items():
        attr_num = attr_name.replace("custom_attribute", "")
        if attr_data.get("populated"):
            analysis["currently_populated"].append({
                "attribute": attr_name,
                "unique_values_sample": attr_data.get("unique_values", [])[:10],
                "sample_size": attr_data.get("sample_size", 0)
            })
            print(f"✓ custom_label_{attr_num}: POPULATED")
            print(f"  Sample values: {', '.join(attr_data.get('unique_values', [])[:5])}")
        else:
            analysis["available_slots"].append(attr_name)
            print(f"○ custom_label_{attr_num}: AVAILABLE")

    print("\n" + "-"*80)
    print("Key Findings:")
    print("-"*80)
    print(f"• {len(analysis['currently_populated'])} custom labels are populated")
    print(f"• {len(analysis['available_slots'])} custom labels are available for use")

    print("\n" + "-"*80)
    print("Important Notes:")
    print("-"*80)
    print("• Custom labels in Google Ads are READ-ONLY via the API")
    print("• Custom labels are SET via Google Merchant Center feed")
    print("• The Google Sheets supplemental feed is used to populate custom labels")
    print("• Custom labels can be used for efficient product segmentation without long IN clauses")

    # Generate recommendations
    if analysis["available_slots"]:
        available_slot = analysis["available_slots"][0]
        slot_num = available_slot.replace("custom_attribute", "")
        analysis["recommendations"].append({
            "slot": f"custom_label_{slot_num}",
            "strategy": "Populate with product_item_id",
            "benefit": "Enable direct product filtering by offer ID",
            "implementation": "Add column to Google Sheets supplemental feed"
        })
        analysis["recommendations"].append({
            "slot": f"custom_label_{slot_num}",
            "strategy": "Populate with category/tier data",
            "benefit": "Enable category-level performance segmentation",
            "implementation": "Map products to categories in feed"
        })

    if analysis["recommendations"]:
        print("\n" + "-"*80)
        print("Recommendations:")
        print("-"*80)
        for i, rec in enumerate(analysis["recommendations"], 1):
            print(f"{i}. Use {rec['slot']} for: {rec['strategy']}")
            print(f"   Benefit: {rec['benefit']}")
            print(f"   How: {rec['implementation']}")

    return analysis


def test_pmax_campaigns(ga_service, customer_id: str) -> dict:
    """Test Performance Max campaign data patterns (DISC-05)."""
    print("\n" + "="*80)
    print("Performance Max Discovery (DISC-05)")
    print("="*80)

    pmax_results = {}

    # Test 1: PMax campaign identification
    print("\nTest 1: PMax Campaign Identification")
    query = """
    SELECT
      campaign.id,
      campaign.name,
      campaign.advertising_channel_type,
      campaign.status
    FROM campaign
    WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
    LIMIT 20
    """
    result = execute_query(ga_service, customer_id, query, "pmax_campaigns")
    pmax_results["campaign_identification"] = result

    if result["success"]:
        active_count = sum(1 for row in result["sample_data"] if row.campaign.status.name == "ENABLED")
        print(f"  ✓ Found {result['row_count']} PMax campaigns ({active_count} active)")
        if result["sample_data"]:
            print(f"    Sample: {result['sample_data'][0].campaign.name}")
    else:
        print(f"  ✗ Error: {result['error']}")

    # Test 2: PMax product-level performance
    print("\nTest 2: PMax Product-Level Performance")
    query = """
    SELECT
      segments.product_item_id,
      segments.date,
      campaign.id,
      campaign.advertising_channel_type,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions,
      metrics.cost_micros
    FROM shopping_performance_view
    WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
      AND segments.date DURING LAST_30_DAYS
      AND metrics.impressions > 0
    ORDER BY metrics.impressions DESC
    LIMIT 20
    """
    result = execute_query(ga_service, customer_id, query, "pmax_product_performance")
    pmax_results["product_level_data"] = result

    if result["success"]:
        print(f"  ✓ Found {result['row_count']} product-level records for PMax")
        if result["sample_data"]:
            top_product = result["sample_data"][0]
            print(f"    Top product: {top_product.segments.product_item_id}")
            print(f"    Impressions: {top_product.metrics.impressions}")
    else:
        print(f"  ✗ Error: {result['error']}")

    # Test 3: PMax asset group data
    print("\nTest 3: PMax Asset Group Data")
    query = """
    SELECT
      asset_group.id,
      asset_group.name,
      asset_group.status,
      asset_group.ad_strength,
      campaign.id
    FROM asset_group
    WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
    LIMIT 20
    """
    result = execute_query(ga_service, customer_id, query, "pmax_asset_groups")
    pmax_results["asset_groups"] = result

    if result["success"]:
        print(f"  ✓ Found {result['row_count']} asset groups")
        if result["sample_data"]:
            print(f"    Sample: {result['sample_data'][0].asset_group.name}")
    else:
        print(f"  ✗ Error: {result['error']}")

    # Test 4: PMax placement data
    print("\nTest 4: PMax Placement Data")
    # Note: performance_max_placement_view has limited metric compatibility
    # Only impressions is widely supported
    query = """
    SELECT
      performance_max_placement_view.display_name,
      performance_max_placement_view.placement,
      performance_max_placement_view.placement_type,
      metrics.impressions
    FROM performance_max_placement_view
    WHERE segments.date DURING LAST_30_DAYS
    ORDER BY metrics.impressions DESC
    LIMIT 20
    """
    result = execute_query(ga_service, customer_id, query, "pmax_placements")
    pmax_results["placements"] = result

    if result["success"]:
        print(f"  ✓ Found {result['row_count']} placement records")
        if result["sample_data"]:
            print(f"    Top placement: {result['sample_data'][0].performance_max_placement_view.placement_type.name}")
            print(f"    Impressions: {result['sample_data'][0].metrics.impressions:,}")
    else:
        print(f"  ✗ Error: {result['error']}")

    # Test 5: PMax vs Standard Shopping comparison
    print("\nTest 5: PMax vs Standard Shopping Comparison")
    query = """
    SELECT
      campaign.advertising_channel_type,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions,
      metrics.cost_micros
    FROM campaign
    WHERE campaign.advertising_channel_type IN ('SHOPPING', 'PERFORMANCE_MAX')
      AND segments.date DURING LAST_30_DAYS
    """
    result = execute_query(ga_service, customer_id, query, "pmax_vs_shopping")
    pmax_results["campaign_comparison"] = result

    if result["success"]:
        # Aggregate by channel type
        by_type = defaultdict(lambda: {"impressions": 0, "clicks": 0, "conversions": 0, "cost": 0})
        for row in result["sample_data"]:
            channel = row.campaign.advertising_channel_type.name
            by_type[channel]["impressions"] += row.metrics.impressions
            by_type[channel]["clicks"] += row.metrics.clicks
            by_type[channel]["conversions"] += row.metrics.conversions
            by_type[channel]["cost"] += row.metrics.cost_micros / 1_000_000

        print(f"  ✓ Comparison data:")
        for channel, metrics in by_type.items():
            print(f"    {channel}:")
            print(f"      Impressions: {metrics['impressions']:,}")
            print(f"      Clicks: {metrics['clicks']:,}")
            print(f"      Conversions: {metrics['conversions']:.1f}")
            print(f"      Cost: ${metrics['cost']:.2f}")
    else:
        print(f"  ✗ Error: {result['error']}")

    return pmax_results


def serialize_row(row) -> dict:
    """Serialize a protobuf row to JSON-compatible dict."""
    # Just return a simple representation
    return {"_note": "Sample data serialization - full protobuf objects not JSON serializable"}


def main():
    """Main discovery script."""
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    print("="*80)
    print("Custom Label & Performance Max Discovery Script")
    print("="*80)
    print(f"Customer ID: {customer_id}")

    client = load_client()
    ga_service = client.get_service("GoogleAdsService")

    # Part A: Custom label discovery
    discovery_results = discover_custom_label_values(ga_service, customer_id)

    # Custom label filtering tests
    filtering_results = test_custom_label_filtering(ga_service, customer_id, discovery_results)

    # Part B: Population strategy analysis
    population_strategy = analyze_population_strategy(discovery_results)

    # Part C: Performance Max discovery
    pmax_results = test_pmax_campaigns(ga_service, customer_id)

    # Compile final results
    final_results = {
        "customer_id": customer_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "custom_label_discovery": {
            "attributes": discovery_results["attributes"],
            "filtering_tests": [
                {k: v for k, v in test.items() if k != "sample_data"}
                for test in filtering_results.get("tests", [])
            ],
            "population_strategy": population_strategy
        },
        "pmax_discovery": {
            "campaign_identification": {
                k: v for k, v in pmax_results["campaign_identification"].items()
                if k != "sample_data"
            },
            "product_level_data": {
                k: v for k, v in pmax_results["product_level_data"].items()
                if k != "sample_data"
            },
            "asset_groups": {
                k: v for k, v in pmax_results["asset_groups"].items()
                if k != "sample_data"
            },
            "placements": {
                k: v for k, v in pmax_results["placements"].items()
                if k != "sample_data"
            },
            "campaign_comparison": {
                k: v for k, v in pmax_results["campaign_comparison"].items()
                if k != "sample_data"
            }
        }
    }

    # Write results to JSON
    output_path = Path(__file__).parent.parent / ".planning" / "phases" / "02-comprehensive-data-discovery" / "disc-03-04-05-results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(final_results, f, indent=2)

    print("\n" + "="*80)
    print(f"✓ Results written to: {output_path}")
    print("="*80)


if __name__ == "__main__":
    main()
