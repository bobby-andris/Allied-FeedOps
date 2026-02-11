#!/usr/bin/env python3
"""Discover available fields in shopping_performance_view."""
from __future__ import annotations

import os
import sys
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


def main():
    """Discover available fields."""
    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

    client = load_client()
    ga_service = client.get_service("GoogleAdsFieldService")

    # Query for shopping_performance_view fields
    # Note: GoogleAdsFieldService doesn't support FROM clause - use WHERE directly
    query = """
    SELECT
      name,
      data_type,
      is_repeated,
      selectable_with
    WHERE name LIKE 'segments.product_%'
    ORDER BY name
    """

    print("Available product-related segments in shopping_performance_view:")
    print("="*80)

    response = ga_service.search_google_ads_fields(query=query)

    for row in response:
        # Check if this field is selectable with shopping_performance_view
        if 'shopping_performance_view' in [str(s) for s in row.selectable_with]:
            print(f"  {row.name:50} {row.data_type.name:15} repeated={row.is_repeated}")


if __name__ == "__main__":
    main()
