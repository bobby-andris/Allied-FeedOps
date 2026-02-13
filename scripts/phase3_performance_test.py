#!/usr/bin/env python3
"""
Phase 3 Performance Testing: Query performance measurement and comprehensive metric retrieval

SAMP-05: Measure query response times across batch sizes (1, 3, 5, 10)
SAMP-06: Validate comprehensive metric retrieval for sample SKUs

Usage:
    python scripts/phase3_performance_test.py --perf-only  # Only performance testing
    python scripts/phase3_performance_test.py              # All tests (perf + comprehensive)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.json_format import MessageToDict

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


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


def load_sample_skus() -> list[dict]:
    """Load sample SKUs from Phase 3 Plan 1 output."""
    sample_file = os.path.join(
        os.path.dirname(__file__),
        "../.planning/phases/03-sample-testing-analysis/sample-skus.json",
    )

    with open(sample_file, "r") as f:
        skus = json.load(f)

    return skus


def measure_query_performance(batch_sizes: list[int], iterations: int = 5) -> dict:
    """
    SAMP-05: Measure query performance across batch sizes.

    Args:
        batch_sizes: List of batch sizes to test (e.g., [1, 3, 5, 10])
        iterations: Number of times to run each query for statistical measurement

    Returns:
        {
            "metadata": {...},
            "results": {
                "1": {"p50_ms": N, "p95_ms": N, ...},
                ...
            },
            "recommendations": {...}
        }
    """
    print("\n" + "=" * 80)
    print("SAMP-05: Query Performance Measurement")
    print("=" * 80)

    client = _load_client()
    customer_id = "6253381786"
    ga_service = client.get_service("GoogleAdsService")

    # Load sample SKUs and extract offer IDs
    sample_skus = load_sample_skus()
    all_offer_ids = [sku["gmc_offer_id"] for sku in sample_skus]

    # Calculate date range (last 30 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    date_range = f"BETWEEN '{start_date}' AND '{end_date}'"

    results = {}

    for batch_size in batch_sizes:
        print(f"\nTesting batch size: {batch_size}")

        # Take first N offer IDs for this batch size
        offer_ids = all_offer_ids[:batch_size]
        in_clause = ", ".join(f"'{oid}'" for oid in offer_ids)

        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          metrics.impressions,
          metrics.clicks,
          metrics.cost_micros,
          metrics.conversions,
          metrics.conversions_value
        FROM shopping_performance_view
        WHERE segments.product_item_id IN ({in_clause})
          AND segments.date {date_range}
        """

        response_times = []
        row_counts = []

        for iteration in range(iterations):
            start = time.perf_counter()

            try:
                stream = ga_service.search_stream(customer_id=customer_id, query=query)

                # Consume all results
                row_count = 0
                for batch in stream:
                    row_count += len(batch.results)

                elapsed_ms = (time.perf_counter() - start) * 1000
                response_times.append(elapsed_ms)
                row_counts.append(row_count)

                print(f"  Iteration {iteration + 1}/{iterations}: {elapsed_ms:.0f}ms, {row_count} rows")

            except GoogleAdsException as ex:
                error_msg = ex.failure.errors[0].message if ex.failure.errors else str(ex)
                print(f"  ❌ Iteration {iteration + 1} failed: {error_msg}")
                continue

        if response_times:
            results[str(batch_size)] = {
                "p50_ms": float(np.percentile(response_times, 50)),
                "p95_ms": float(np.percentile(response_times, 95)),
                "p99_ms": float(np.percentile(response_times, 99)),
                "min_ms": float(np.min(response_times)),
                "max_ms": float(np.max(response_times)),
                "mean_ms": float(np.mean(response_times)),
                "avg_rows": float(np.mean(row_counts)),
            }

    # Print performance table
    print("\n" + "=" * 80)
    print("Performance Summary")
    print("=" * 80)
    print(f"{'Batch Size':<12} {'p50 (ms)':<12} {'p95 (ms)':<12} {'p99 (ms)':<12} {'Avg Rows':<12}")
    print("-" * 80)

    for batch_size in batch_sizes:
        if str(batch_size) in results:
            r = results[str(batch_size)]
            print(
                f"{batch_size:<12} {r['p50_ms']:<12.0f} {r['p95_ms']:<12.0f} {r['p99_ms']:<12.0f} {r['avg_rows']:<12.0f}"
            )

    # Calculate recommendations
    # Choose batch size with best p95 performance
    best_batch_size = None
    best_p95 = float("inf")

    for batch_size_str, perf in results.items():
        if perf["p95_ms"] / int(batch_size_str) < best_p95 / (best_batch_size or 1):
            best_batch_size = int(batch_size_str)
            best_p95 = perf["p95_ms"]

    # Estimate total backfill time for 2,784 SKUs
    total_skus = 2784
    if best_batch_size:
        total_queries = int(np.ceil(total_skus / best_batch_size))
        # Add 20% overhead for rate limiting delays
        estimated_seconds = (total_queries * best_p95 / 1000) * 1.2
        estimated_minutes = estimated_seconds / 60

        recommendations = {
            "optimal_batch_size": best_batch_size,
            "estimated_total_time_minutes": round(estimated_minutes, 1),
            "reasoning": (
                f"Batch size {best_batch_size} provides best throughput "
                f"(p95={best_p95:.0f}ms). Estimated {total_queries} queries "
                f"for {total_skus} SKUs with 20% rate limit overhead."
            ),
        }
    else:
        recommendations = {
            "optimal_batch_size": None,
            "estimated_total_time_minutes": None,
            "reasoning": "No successful queries completed",
        }

    print("\n" + "=" * 80)
    print("Recommendations")
    print("=" * 80)
    print(f"Optimal batch size: {recommendations['optimal_batch_size']}")
    print(f"Estimated total time: {recommendations['estimated_total_time_minutes']} minutes")
    print(f"Reasoning: {recommendations['reasoning']}")

    return {
        "metadata": {
            "date": datetime.now().date().isoformat(),
            "iterations_per_batch": iterations,
            "customer_id": customer_id,
        },
        "results": results,
        "recommendations": recommendations,
    }


def fetch_comprehensive_metrics(sample_skus: list[dict]) -> dict:
    """
    SAMP-06: Fetch comprehensive metrics for sample SKUs.

    Tests all metric groups identified in Phase 2:
    - Core: impressions, clicks, ctr, cost, cpc, cpm
    - Conversions: conversions, conversion_value, cvr, cpa
    - Shopping cart: orders, avg_cart_size, avg_order_value, revenue, units_sold
    - Competitive: impression_share, click_share, budget_lost_is, rank_lost_is

    Args:
        sample_skus: List of SKU dicts from sample-skus.json

    Returns:
        {
            "metadata": {...},
            "metric_availability": {...},
            "skus": {...}
        }
    """
    print("\n" + "=" * 80)
    print("SAMP-06: Comprehensive Metric Retrieval")
    print("=" * 80)

    client = _load_client()
    customer_id = "6253381786"
    ga_service = client.get_service("GoogleAdsService")

    # Calculate date range (last 30 days)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    date_range = f"BETWEEN '{start_date}' AND '{end_date}'"

    # Test metric groups
    # NOTE: conversions_value_per_cost is known to be incompatible (Phase 2 Decision 8)
    # NOTE: average_cpm, search_budget_lost_impression_share, search_rank_lost_impression_share
    #       are incompatible with shopping_performance_view (discovered in SAMP-06)
    metric_groups = {
        "core": [
            "metrics.impressions",
            "metrics.clicks",
            "metrics.ctr",
            "metrics.cost_micros",
            "metrics.average_cpc",
            # "metrics.average_cpm",  # Incompatible with shopping_performance_view
        ],
        "conversions": [
            "metrics.conversions",
            "metrics.conversions_value",
            "metrics.conversions_from_interactions_rate",
            "metrics.cost_per_conversion",
        ],
        "shopping_cart": [
            "metrics.orders",
            "metrics.average_cart_size",
            "metrics.average_order_value_micros",
            "metrics.revenue_micros",
            "metrics.units_sold",
        ],
        "competitive": [
            "metrics.search_impression_share",
            "metrics.search_click_share",
            # "metrics.search_budget_lost_impression_share",  # Incompatible with shopping_performance_view
            # "metrics.search_rank_lost_impression_share",  # Incompatible with shopping_performance_view
        ],
    }

    # Build comprehensive query
    all_metrics = []
    for group_metrics in metric_groups.values():
        all_metrics.extend(group_metrics)

    metric_availability = {}
    sku_data = {}

    # Try fetching comprehensive metrics for each SKU
    for sku in sample_skus:
        master_sku = sku["master_sku"]
        offer_id = sku["gmc_offer_id"]

        print(f"\nFetching metrics for {master_sku} ({offer_id})...")

        # First, try all metrics together
        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          {', '.join(all_metrics)}
        FROM shopping_performance_view
        WHERE segments.product_item_id = '{offer_id}'
          AND segments.date {date_range}
        """

        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            # Aggregate metrics across all days
            days_with_data = 0
            aggregated = {
                "core": {},
                "conversions": {},
                "shopping_cart": {},
                "competitive": {},
            }

            for batch in stream:
                for row in batch.results:
                    days_with_data += 1
                    row_dict = MessageToDict(row._pb, preserving_proto_field_name=True)
                    metrics = row_dict.get("metrics", {})

                    # Sum counts, collect rates for averaging
                    for group, group_metrics in metric_groups.items():
                        if group not in aggregated:
                            aggregated[group] = {}

                        for metric_path in group_metrics:
                            metric_name = metric_path.split(".")[-1]
                            value = metrics.get(metric_name)

                            if value is not None:
                                if metric_name not in aggregated[group]:
                                    aggregated[group][metric_name] = []
                                aggregated[group][metric_name].append(value)

            # Calculate final aggregated values
            final_aggregated = {}
            for group, metrics_dict in aggregated.items():
                final_aggregated[group] = {}
                for metric_name, values in metrics_dict.items():
                    if not values:
                        continue

                    # Convert to numeric (handle string values from protobuf)
                    try:
                        numeric_values = [float(v) for v in values]
                    except (ValueError, TypeError):
                        # Skip non-numeric values
                        continue

                    # Sum for counts/totals, average for rates
                    if any(
                        keyword in metric_name
                        for keyword in ["rate", "share", "ctr", "average", "avg"]
                    ):
                        final_aggregated[group][metric_name] = float(np.mean(numeric_values))
                    else:
                        final_aggregated[group][metric_name] = float(np.sum(numeric_values))

            sku_data[master_sku] = {
                "offer_id": offer_id,
                "days_with_data": days_with_data,
                **final_aggregated,
            }

            print(f"  ✅ Success: {days_with_data} days of data")
            print(f"     Core metrics: {len(final_aggregated.get('core', {}))}")
            print(f"     Conversion metrics: {len(final_aggregated.get('conversions', {}))}")
            print(f"     Shopping cart metrics: {len(final_aggregated.get('shopping_cart', {}))}")
            print(f"     Competitive metrics: {len(final_aggregated.get('competitive', {}))}")

        except GoogleAdsException as ex:
            error_msg = ex.failure.errors[0].message if ex.failure.errors else str(ex)
            print(f"  ❌ Query failed: {error_msg}")

            # Try each metric group separately to identify which ones work
            print("  Testing metric groups individually...")

            for group, group_metrics in metric_groups.items():
                query = f"""
                SELECT
                  segments.product_item_id,
                  {', '.join(group_metrics)}
                FROM shopping_performance_view
                WHERE segments.product_item_id = '{offer_id}'
                  AND segments.date {date_range}
                LIMIT 1
                """

                try:
                    stream = ga_service.search_stream(customer_id=customer_id, query=query)
                    for _ in stream:
                        pass  # Just test if query works
                    print(f"    ✅ {group}: Available")
                    if group not in metric_availability:
                        metric_availability[group] = {"available": True, "skus_with_data": 0}
                except GoogleAdsException:
                    print(f"    ❌ {group}: Not available")
                    if group not in metric_availability:
                        metric_availability[group] = {
                            "available": False,
                            "skus_with_data": 0,
                            "note": "Metric group incompatible with shopping_performance_view",
                        }

    # Calculate metric availability summary
    for group in metric_groups.keys():
        if group not in metric_availability:
            # Count SKUs with data for this group
            skus_with_data = sum(
                1 for sku_metrics in sku_data.values() if sku_metrics.get(group)
            )
            metric_availability[group] = {
                "available": skus_with_data > 0,
                "skus_with_data": skus_with_data,
            }

    print("\n" + "=" * 80)
    print("Metric Availability Summary")
    print("=" * 80)

    for group, availability in metric_availability.items():
        status = "✅ Available" if availability["available"] else "❌ Not Available"
        sku_count = availability["skus_with_data"]
        print(f"{group:<20} {status:<20} ({sku_count}/{len(sample_skus)} SKUs with data)")
        if "note" in availability:
            print(f"  Note: {availability['note']}")

    return {
        "metadata": {"date": datetime.now().date().isoformat(), "lookback_days": 30},
        "metric_availability": metric_availability,
        "skus": sku_data,
    }


def main():
    parser = argparse.ArgumentParser(description="Phase 3 Performance Testing")
    parser.add_argument(
        "--perf-only",
        action="store_true",
        help="Run only performance measurement (SAMP-05)",
    )
    args = parser.parse_args()

    # Load sample SKUs
    sample_skus = load_sample_skus()
    print(f"Loaded {len(sample_skus)} sample SKUs")

    # SAMP-05: Query performance measurement
    performance_results = measure_query_performance(batch_sizes=[1, 3, 5, 10], iterations=5)

    # Save performance results
    perf_output = os.path.join(
        os.path.dirname(__file__),
        "../.planning/phases/03-sample-testing-analysis/query-performance.json",
    )
    with open(perf_output, "w") as f:
        json.dump(performance_results, f, indent=2)
    print(f"\n✅ Performance results saved to: {perf_output}")

    if not args.perf_only:
        # SAMP-06: Comprehensive metric retrieval
        comprehensive_results = fetch_comprehensive_metrics(sample_skus)

        # Save comprehensive results
        comp_output = os.path.join(
            os.path.dirname(__file__),
            "../.planning/phases/03-sample-testing-analysis/comprehensive-metrics.json",
        )
        with open(comp_output, "w") as f:
            json.dump(comprehensive_results, f, indent=2)
        print(f"✅ Comprehensive results saved to: {comp_output}")

    print("\n" + "=" * 80)
    print("✅ Phase 3 Performance Testing Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
