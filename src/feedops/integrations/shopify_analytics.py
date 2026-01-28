"""Shopify Analytics API integration.

Fetches product analytics (views, add-to-carts, purchases) from Shopify.

Note: Shopify's native analytics API has limitations. This module provides:
1. Shopify Analytics API (if available on your plan)
2. Order-based conversion calculation (fallback)

For comprehensive e-commerce analytics, consider using GA4 data via
the Analytics MCP server.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

SHOPIFY_API_VERSION_DEFAULT = "2026-01"

# GraphQL query for product analytics (Shopify Plus / Advanced plans)
SHOPIFY_PRODUCT_ANALYTICS_QUERY = """
query ProductAnalytics($productId: ID!, $startDate: DateTime!, $endDate: DateTime!) {
  product(id: $productId) {
    id
    title
    analytics: analyticsData(timeRange: {startDate: $startDate, endDate: $endDate}) {
      pageViews
      uniqueVisitors
      addToCarts
      conversions
      revenue {
        amount
        currencyCode
      }
    }
  }
}
"""

# Fallback: Order-based analytics query
SHOPIFY_ORDERS_QUERY = """
query OrdersForProduct($productId: ID!, $first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    nodes {
      id
      createdAt
      totalPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
      lineItems(first: 50) {
        nodes {
          product {
            id
          }
          quantity
          originalTotalSet {
            shopMoney {
              amount
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def _normalize_store_host(store_url: str) -> str:
    """Normalize store URL to hostname."""
    parsed = urlparse(store_url)
    if parsed.netloc:
        return parsed.netloc
    return store_url.replace("https://", "").replace("http://", "").strip("/")


def _product_gid(product_id: str) -> str:
    """Ensure product ID is in GID format."""
    if product_id.startswith("gid://"):
        return product_id
    return f"gid://shopify/Product/{product_id}"


def _empty_analytics_result() -> dict[str, Any]:
    """Return an empty analytics result structure."""
    return {
        "views": 0,
        "unique_visitors": 0,
        "add_to_carts": 0,
        "purchases": 0,
        "revenue": 0.0,
        "conversion_rate": 0.0,
        "data_source": "none",
    }


def fetch_shopify_product_analytics(
    product_id: str,
    start_date: str,
    end_date: str,
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch Shopify product analytics.

    Tries Shopify Analytics API first, falls back to order-based calculation.

    Args:
        product_id: Shopify product ID (numeric or GID format).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        store_url: Shopify store URL (e.g., 'yourstore.myshopify.com').
        access_token: Shopify Admin API access token.
        env: Environment variables mapping.

    Returns:
        Dictionary with analytics metrics:
        {
            'views': int,
            'unique_visitors': int,
            'add_to_carts': int,
            'purchases': int,
            'revenue': float,
            'conversion_rate': float (views → purchases),
            'data_source': str ('analytics_api', 'orders', 'none')
        }

    Raises:
        ValueError: If credentials are missing.
    """
    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    gid = _product_gid(product_id)

    # Try Analytics API first (requires Shopify Plus or Advanced)
    try:
        result = _fetch_via_analytics_api(
            gid,
            start_date,
            end_date,
            store_url=store_url,
            access_token=access_token,
            env=env,
        )
        if result.get("data_source") == "analytics_api":
            return result
    except Exception as e:
        logger.debug("Analytics API not available: %s", e)

    # Fall back to order-based calculation
    try:
        return _fetch_via_orders(
            gid,
            start_date,
            end_date,
            store_url=store_url,
            access_token=access_token,
            env=env,
        )
    except Exception as e:
        logger.error("Failed to fetch order-based analytics: %s", e)
        return _empty_analytics_result()


def _fetch_via_analytics_api(
    product_gid: str,
    start_date: str,
    end_date: str,
    *,
    store_url: str,
    access_token: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch analytics using Shopify Analytics API.

    Note: This requires Shopify Plus or Advanced plan and appropriate scopes.
    """
    env = env or os.environ
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    # Convert dates to ISO format with time
    start_dt = f"{start_date}T00:00:00Z"
    end_dt = f"{end_date}T23:59:59Z"

    variables = {
        "productId": product_gid,
        "startDate": start_dt,
        "endDate": end_dt,
    }

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.post(
            endpoint,
            json={"query": SHOPIFY_PRODUCT_ANALYTICS_QUERY, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        # Analytics API not available - return empty to trigger fallback
        raise ValueError(f"Analytics API error: {payload['errors']}")

    data = payload.get("data", {})
    product = data.get("product", {})
    analytics = product.get("analytics") or product.get("analyticsData")

    if not analytics:
        # No analytics data available
        raise ValueError("Analytics data not available for this product")

    views = int(analytics.get("pageViews", 0) or 0)
    unique_visitors = int(analytics.get("uniqueVisitors", 0) or 0)
    add_to_carts = int(analytics.get("addToCarts", 0) or 0)
    conversions = int(analytics.get("conversions", 0) or 0)

    revenue_data = analytics.get("revenue", {})
    revenue = float(revenue_data.get("amount", 0) or 0)

    conversion_rate = conversions / views if views > 0 else 0.0

    return {
        "views": views,
        "unique_visitors": unique_visitors,
        "add_to_carts": add_to_carts,
        "purchases": conversions,
        "revenue": revenue,
        "conversion_rate": conversion_rate,
        "data_source": "analytics_api",
    }


def _fetch_via_orders(
    product_gid: str,
    start_date: str,
    end_date: str,
    *,
    store_url: str,
    access_token: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Calculate analytics from order data.

    This is a fallback that calculates purchases and revenue from orders.
    Views and add-to-carts are not available via this method.
    """
    env = env or os.environ
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    # Build order query for date range
    order_query = (
        f"created_at:>={start_date} created_at:<={end_date} financial_status:paid"
    )

    total_purchases = 0
    total_revenue = 0.0
    after: str | None = None

    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        while True:
            variables = {
                "productId": product_gid,
                "first": 50,
                "after": after,
                "query": order_query,
            }

            response = client.post(
                endpoint,
                json={"query": SHOPIFY_ORDERS_QUERY, "variables": variables},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()

            if payload.get("errors"):
                logger.warning("Order query errors: %s", payload["errors"])
                break

            data = payload.get("data", {})
            orders = data.get("orders", {})
            nodes = orders.get("nodes", [])

            for order in nodes:
                line_items = order.get("lineItems", {}).get("nodes", [])
                for item in line_items:
                    item_product = item.get("product", {})
                    if item_product and item_product.get("id") == product_gid:
                        quantity = int(item.get("quantity", 0) or 0)
                        total_purchases += quantity

                        amount_data = item.get("originalTotalSet", {}).get(
                            "shopMoney", {}
                        )
                        amount = float(amount_data.get("amount", 0) or 0)
                        total_revenue += amount

            page_info = orders.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

    return {
        "views": 0,  # Not available via orders
        "unique_visitors": 0,  # Not available via orders
        "add_to_carts": 0,  # Not available via orders
        "purchases": total_purchases,
        "revenue": total_revenue,
        "conversion_rate": 0.0,  # Cannot calculate without views
        "data_source": "orders",
    }


def fetch_batch_shopify_analytics(
    product_ids: list[str],
    start_date: str,
    end_date: str,
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch analytics for multiple products.

    Args:
        product_ids: List of Shopify product IDs.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        store_url: Shopify store URL.
        access_token: Shopify Admin API access token.
        env: Environment variables mapping.

    Returns:
        Dictionary mapping product_id to analytics metrics.
    """
    results: dict[str, dict[str, Any]] = {}

    for product_id in product_ids:
        try:
            result = fetch_shopify_product_analytics(
                product_id,
                start_date,
                end_date,
                store_url=store_url,
                access_token=access_token,
                env=env,
            )
            results[product_id] = result
        except Exception as e:
            logger.error("Failed to fetch analytics for product %s: %s", product_id, e)
            results[product_id] = _empty_analytics_result()

    return results


def calculate_shopify_metrics_from_orders(
    product_id: str,
    start_date: str,
    end_date: str,
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Calculate conversion metrics from order data only.

    This is useful when:
    - You don't have Shopify Analytics API access
    - You want order-based metrics specifically
    - You're correlating with external traffic data (e.g., GA4)

    Returns metrics that can be combined with external traffic data.
    """
    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    gid = _product_gid(product_id)

    return _fetch_via_orders(
        gid,
        start_date,
        end_date,
        store_url=store_url,
        access_token=access_token,
        env=env,
    )
