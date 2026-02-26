#!/usr/bin/env python3
"""Google Ads account audit for Phase 34.2-02.

Queries conversion actions, CPA, CPC caps, behavioral signals, impression share.
"""
import json
import sys
import os
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from google.ads.googleads.client import GoogleAdsClient

CUSTOMER_ID = "6253381786"

# Date ranges
TODAY = date.today()
DATE_90_AGO = (TODAY - timedelta(days=90)).strftime("%Y-%m-%d")
DATE_30_AGO = (TODAY - timedelta(days=30)).strftime("%Y-%m-%d")
DATE_TODAY = TODAY.strftime("%Y-%m-%d")


def run_query(client, query, label=""):
    """Run a GAQL query and return results as list of dicts."""
    service = client.get_service("GoogleAdsService")
    results = []
    try:
        response = service.search(customer_id=CUSTOMER_ID, query=query)
        for row in response:
            results.append(row)
        print(f"  [{label}] Got {len(results)} rows")
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
    return results


def main():
    client = GoogleAdsClient.load_from_storage()
    output = {}

    # 1. Conversion actions
    print("1. Querying conversion actions...")
    query1 = """
        SELECT conversion_action.name, conversion_action.type,
               conversion_action.category, conversion_action.status,
               conversion_action.counting_type,
               conversion_action.include_in_conversions_metric
        FROM conversion_action
        WHERE conversion_action.status = ENABLED
    """
    rows = run_query(client, query1, "conversion_actions")
    conversions = []
    for r in rows:
        ca = r.conversion_action
        conversions.append({
            "name": ca.name,
            "type": ca.type_.name,
            "category": ca.category.name,
            "counting_type": ca.counting_type.name,
            "include_in_conversions": ca.include_in_conversions_metric,
        })
    output["conversion_actions"] = conversions

    # 2. Campaign metrics (last 90 days) for CPA
    print("2. Querying campaign metrics (90 days)...")
    query2 = f"""
        SELECT campaign.name, metrics.cost_micros, metrics.conversions,
               metrics.all_conversions
        FROM campaign
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND segments.date BETWEEN '{DATE_90_AGO}' AND '{DATE_TODAY}'
    """
    rows = run_query(client, query2, "campaign_metrics")
    campaigns = []
    total_cost_micros = 0
    total_conversions = 0.0
    total_all_conversions = 0.0
    for r in rows:
        c = r.campaign
        m = r.metrics
        campaigns.append({
            "name": c.name,
            "cost_micros": m.cost_micros,
            "conversions": m.conversions,
            "all_conversions": m.all_conversions,
        })
        total_cost_micros += m.cost_micros
        total_conversions += m.conversions
        total_all_conversions += m.all_conversions
    output["campaign_metrics"] = campaigns
    output["totals"] = {
        "total_cost_micros": total_cost_micros,
        "total_cost_dollars": total_cost_micros / 1_000_000,
        "total_conversions": total_conversions,
        "total_all_conversions": total_all_conversions,
        "avg_cpa": (total_cost_micros / 1_000_000 / total_conversions) if total_conversions > 0 else None,
        "avg_micro_cpa": (total_cost_micros / 1_000_000 / total_all_conversions) if total_all_conversions > 0 else None,
    }

    # 3. CPC caps per ad group
    print("3. Querying CPC caps per ad group...")
    query3 = """
        SELECT campaign.name, ad_group.name, ad_group.cpc_bid_micros
        FROM ad_group
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND ad_group.status = ENABLED
    """
    rows = run_query(client, query3, "cpc_caps")
    ad_groups = []
    for r in rows:
        ad_groups.append({
            "campaign_name": r.campaign.name,
            "ad_group_name": r.ad_group.name,
            "cpc_bid_micros": r.ad_group.cpc_bid_micros,
            "cpc_bid_dollars": r.ad_group.cpc_bid_micros / 1_000_000 if r.ad_group.cpc_bid_micros else 0,
        })
    output["ad_group_cpc_caps"] = ad_groups

    # 4. Behavioral signal availability (search_term_view sample)
    print("4. Querying search_term_view sample (behavioral signals)...")
    query4 = f"""
        SELECT search_term_view.search_term, metrics.impressions, metrics.clicks,
               metrics.average_cpc, metrics.all_conversions, metrics.conversions,
               metrics.cross_device_conversions
        FROM search_term_view
        WHERE campaign.advertising_channel_type = SHOPPING
          AND segments.date BETWEEN '{DATE_30_AGO}' AND '{DATE_TODAY}'
        ORDER BY metrics.clicks DESC
        LIMIT 20
    """
    rows = run_query(client, query4, "behavioral_signals")
    signals = []
    signal_availability = {
        "impressions": False,
        "clicks": False,
        "average_cpc": False,
        "all_conversions": False,
        "conversions": False,
        "cross_device_conversions": False,
    }
    for r in rows:
        m = r.metrics
        row_data = {
            "search_term": r.search_term_view.search_term,
            "impressions": m.impressions,
            "clicks": m.clicks,
            "average_cpc": m.average_cpc,
            "all_conversions": m.all_conversions,
            "conversions": m.conversions,
            "cross_device_conversions": m.cross_device_conversions,
        }
        signals.append(row_data)
        for k in signal_availability:
            val = row_data[k]
            if val is not None and val != 0:
                signal_availability[k] = True
    output["behavioral_signal_sample"] = signals
    output["signal_availability"] = signal_availability

    # 5. Campaign impression share
    print("5. Querying campaign impression share...")
    query5 = f"""
        SELECT campaign.name, metrics.search_impression_share
        FROM campaign
        WHERE campaign.advertising_channel_type = SHOPPING
          AND campaign.status = ENABLED
          AND segments.date BETWEEN '{DATE_30_AGO}' AND '{DATE_TODAY}'
    """
    rows = run_query(client, query5, "impression_share")
    impression_shares = []
    for r in rows:
        impression_shares.append({
            "campaign_name": r.campaign.name,
            "search_impression_share": r.metrics.search_impression_share,
        })
    output["impression_shares"] = impression_shares

    # Write raw JSON for processing
    outpath = os.path.join(os.path.dirname(__file__), '..', 'docs', 'analysis', '_audit_raw.json')
    with open(outpath, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nRaw data written to {outpath}")

    # Print summary
    print("\n=== SUMMARY ===")
    print(f"Conversion actions: {len(conversions)}")
    print(f"Shopping campaigns: {len(set(c['name'] for c in campaigns))}")
    t = output["totals"]
    print(f"Total spend (90d): ${t['total_cost_dollars']:.2f}")
    print(f"Total conversions: {t['total_conversions']:.1f}")
    print(f"Total all_conversions: {t['total_all_conversions']:.1f}")
    if t['avg_cpa']:
        print(f"Avg CPA: ${t['avg_cpa']:.2f}")
    if t['avg_micro_cpa']:
        print(f"Avg micro-CPA: ${t['avg_micro_cpa']:.2f}")
    print(f"Ad groups with CPC caps: {len(ad_groups)}")
    print(f"Signal availability: {signal_availability}")
    print(f"Impression share entries: {len(impression_shares)}")


if __name__ == "__main__":
    main()
