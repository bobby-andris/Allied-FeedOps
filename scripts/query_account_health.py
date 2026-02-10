#!/usr/bin/env python3
"""Query Google Ads account health metrics for team data gathering."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from feedops.integrations.google_ads_performance import _load_client, _run_gaql_query

def main():
    customer_id = "6253381786"

    # Load client
    client = _load_client()

    # Query 1: Last 30 days
    print("=" * 80)
    print("LAST 30 DAYS ACCOUNT SUMMARY")
    print("=" * 80)
    query_30d = """
        SELECT
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING LAST_30_DAYS
    """

    results_30d = _run_gaql_query(client, customer_id, query_30d)
    print(f"\nFound {len(results_30d)} campaigns\n")

    # Calculate totals
    total_30d = {
        'impressions': 0,
        'clicks': 0,
        'cost_micros': 0,
        'conversions': 0,
        'conversions_value': 0
    }

    for row in results_30d:
        metrics = row.get('metrics', {})
        campaign = row.get('campaign', {})

        impressions = int(metrics.get('impressions', 0))
        clicks = int(metrics.get('clicks', 0))
        cost_micros = int(metrics.get('cost_micros', 0))
        conversions = float(metrics.get('conversions', 0))
        conversions_value = float(metrics.get('conversions_value', 0))

        total_30d['impressions'] += impressions
        total_30d['clicks'] += clicks
        total_30d['cost_micros'] += cost_micros
        total_30d['conversions'] += conversions
        total_30d['conversions_value'] += conversions_value

        print(f"Campaign: {campaign.get('name', 'Unknown')}")
        print(f"  Impressions: {impressions:,}")
        print(f"  Clicks: {clicks:,}")
        print(f"  Cost: ${cost_micros / 1_000_000:,.2f}")
        print(f"  Conversions: {conversions:.2f}")
        print(f"  Revenue: ${conversions_value:,.2f}")
        print()

    # Query 2: Last 7 days
    print("\n" + "=" * 80)
    print("LAST 7 DAYS ACCOUNT SUMMARY")
    print("=" * 80)
    query_7d = """
        SELECT
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date DURING LAST_7_DAYS
    """

    results_7d = _run_gaql_query(client, customer_id, query_7d)
    print(f"\nFound {len(results_7d)} campaigns\n")

    # Calculate totals
    total_7d = {
        'impressions': 0,
        'clicks': 0,
        'cost_micros': 0,
        'conversions': 0,
        'conversions_value': 0
    }

    for row in results_7d:
        metrics = row.get('metrics', {})
        campaign = row.get('campaign', {})

        impressions = int(metrics.get('impressions', 0))
        clicks = int(metrics.get('clicks', 0))
        cost_micros = int(metrics.get('cost_micros', 0))
        conversions = float(metrics.get('conversions', 0))
        conversions_value = float(metrics.get('conversions_value', 0))

        total_7d['impressions'] += impressions
        total_7d['clicks'] += clicks
        total_7d['cost_micros'] += cost_micros
        total_7d['conversions'] += conversions
        total_7d['conversions_value'] += conversions_value

        print(f"Campaign: {campaign.get('name', 'Unknown')}")
        print(f"  Impressions: {impressions:,}")
        print(f"  Clicks: {clicks:,}")
        print(f"  Cost: ${cost_micros / 1_000_000:,.2f}")
        print(f"  Conversions: {conversions:.2f}")
        print(f"  Revenue: ${conversions_value:,.2f}")
        print()

    # Print summary with calculations
    print("\n" + "=" * 80)
    print("ACCOUNT HEALTH METRICS")
    print("=" * 80)

    def print_period_summary(period_name, totals):
        cost = totals['cost_micros'] / 1_000_000
        impressions = totals['impressions']
        clicks = totals['clicks']
        conversions = totals['conversions']
        revenue = totals['conversions_value']

        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cvr = (conversions / clicks * 100) if clicks > 0 else 0
        roas = (revenue / cost) if cost > 0 else 0

        print(f"\n{period_name}:")
        print(f"  Total Impressions: {impressions:,}")
        print(f"  Total Clicks: {clicks:,}")
        print(f"  Total Cost: ${cost:,.2f}")
        print(f"  Total Conversions: {conversions:.2f}")
        print(f"  Total Revenue: ${revenue:,.2f}")
        print(f"  CTR: {ctr:.2f}%")
        print(f"  CVR: {cvr:.2f}%")
        print(f"  ROAS: {roas:.2f}x")

        # Alerts
        alerts = []
        if roas < 3.0:
            alerts.append("🔴 ROAS < 3x")
        if ctr < 1.0:
            alerts.append("🔴 CTR < 1%")
        if cvr < 2.0:
            alerts.append("🔴 CVR < 2%")

        if alerts:
            print(f"  ALERTS: {', '.join(alerts)}")
        else:
            print("  ✅ All metrics healthy")

    print_period_summary("LAST 30 DAYS", total_30d)
    print_period_summary("LAST 7 DAYS", total_7d)
    print()

if __name__ == "__main__":
    main()
