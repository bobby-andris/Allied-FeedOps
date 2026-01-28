"""Bing Ads Performance API integration.

Fetches shopping performance metrics (impressions, clicks, conversions, ROAS) for
products via the Bing Ads Reporting API.

Uses the ProductDimensionPerformanceReport for Shopping campaigns.
Ref: https://learn.microsoft.com/en-us/advertising/reporting-service/productdimensionperformancereportrequest

This module requires the bingads Python SDK and OAuth2 credentials.
"""

from __future__ import annotations

import csv
import logging
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _truthy_env(name: str) -> str | None:
    """Get truthy environment variable value."""
    val = os.getenv(name)
    if not val:
        return None
    val = val.strip()
    return val or None


def _api_enabled() -> bool:
    """Check if Bing Ads API is enabled."""
    return os.getenv("BING_ADS_API_ENABLED", "").lower() in {"1", "true", "yes"}


def _empty_performance_result() -> dict[str, Any]:
    """Return an empty performance result structure."""
    return {
        "impressions": 0,
        "clicks": 0,
        "ctr": 0.0,
        "conversions": 0,
        "conversion_value": 0.0,
        "cost": 0.0,
        "roas": 0.0,
        "daily_data": [],
    }


def _get_authorization_data():
    """Get Bing Ads authorization data from environment.

    Required environment variables:
    - BING_ADS_DEVELOPER_TOKEN
    - BING_ADS_CLIENT_ID
    - BING_ADS_CLIENT_SECRET (optional for some flows)
    - BING_ADS_REFRESH_TOKEN
    - BING_ADS_CUSTOMER_ID
    - BING_ADS_ACCOUNT_ID
    """
    # Lazy import to keep bingads optional
    from bingads.authorization import (  # type: ignore[import-not-found]
        AuthorizationData,
        OAuthDesktopMobileAuthCodeGrant,
        OAuthWebAuthCodeGrant,
    )

    developer_token = _truthy_env("BING_ADS_DEVELOPER_TOKEN")
    client_id = _truthy_env("BING_ADS_CLIENT_ID")
    client_secret = _truthy_env("BING_ADS_CLIENT_SECRET")
    refresh_token = _truthy_env("BING_ADS_REFRESH_TOKEN")

    if not developer_token:
        raise ValueError("BING_ADS_DEVELOPER_TOKEN is required")
    if not client_id:
        raise ValueError("BING_ADS_CLIENT_ID is required")
    if not refresh_token:
        raise ValueError("BING_ADS_REFRESH_TOKEN is required")

    # Use web or desktop grant depending on whether we have client secret
    if client_secret:
        authentication = OAuthWebAuthCodeGrant(
            client_id=client_id,
            client_secret=client_secret,
            redirection_uri="",
        )
    else:
        authentication = OAuthDesktopMobileAuthCodeGrant(
            client_id=client_id,
        )

    # Request refresh
    authentication.request_oauth_tokens_by_refresh_token(refresh_token)

    authorization_data = AuthorizationData(
        account_id=_truthy_env("BING_ADS_ACCOUNT_ID"),
        customer_id=_truthy_env("BING_ADS_CUSTOMER_ID"),
        developer_token=developer_token,
        authentication=authentication,
    )

    return authorization_data


def _get_reporting_service(authorization_data):
    """Create Bing Ads Reporting Service client."""
    from bingads.v13.reporting import ReportingServiceManager  # type: ignore[import-not-found]

    return ReportingServiceManager(
        authorization_data=authorization_data,
        poll_interval_in_milliseconds=5000,
        environment="production",
    )


def fetch_bing_product_performance(
    offer_id: str,
    start_date: str,
    end_date: str,
    *,
    customer_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Fetch Bing Shopping performance metrics for a product.

    Uses Bing Ads Reporting API - ProductDimensionPerformanceReport.

    Args:
        offer_id: Product offer ID in Bing catalog (e.g., SKU).
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        customer_id: Bing Ads customer ID (falls back to env var).
        account_id: Bing Ads account ID (falls back to env var).

    Returns:
        Dictionary with aggregated metrics:
        {
            'impressions': int,
            'clicks': int,
            'ctr': float (0.0 to 1.0),
            'conversions': int,
            'conversion_value': float,
            'cost': float,
            'roas': float,
            'daily_data': list[dict]
        }

    Raises:
        ValueError: If API is not enabled or credentials are missing.
    """
    customer_id = customer_id or _truthy_env("BING_ADS_CUSTOMER_ID")
    account_id = account_id or _truthy_env("BING_ADS_ACCOUNT_ID")

    if not _api_enabled():
        logger.warning(
            "Bing Ads API is not enabled. Set BING_ADS_API_ENABLED=1 to fetch "
            "performance metrics."
        )
        return _empty_performance_result()

    if not customer_id or not account_id:
        raise ValueError("BING_ADS_CUSTOMER_ID and BING_ADS_ACCOUNT_ID are required.")

    try:
        return _fetch_performance_via_api(
            offer_id=offer_id,
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            account_id=account_id,
        )
    except ImportError as e:
        logger.error("bingads SDK not installed. Run: pip install bingads>=14.0")
        raise ValueError("bingads SDK required for Bing performance fetching") from e
    except Exception as e:
        logger.error("Failed to fetch Bing performance for %s: %s", offer_id, e)
        raise ValueError(f"Failed to fetch Bing performance: {e}") from e


def _fetch_performance_via_api(
    *,
    offer_id: str,
    start_date: str,
    end_date: str,
    customer_id: str,
    account_id: str,
) -> dict[str, Any]:
    """Fetch performance metrics using Bing Ads Reporting API.

    Uses ProductDimensionPerformanceReport to get Shopping campaign metrics.
    """
    from bingads.service_client import ServiceClient  # type: ignore[import-not-found]
    from bingads.v13.reporting import ReportingDownloadParameters  # type: ignore[import-not-found]

    authorization_data = _get_authorization_data()

    # Override with passed parameters
    if customer_id:
        authorization_data.customer_id = customer_id
    if account_id:
        authorization_data.account_id = account_id

    # Create service client for direct SOAP calls
    reporting_service = ServiceClient(
        service="ReportingService",
        version=13,
        authorization_data=authorization_data,
        environment="production",
    )

    # Build report request
    report_request = _build_product_performance_report(
        reporting_service=reporting_service,
        account_id=int(account_id),
        start_date=start_date,
        end_date=end_date,
    )

    # Submit and download report
    report_data = _download_report(reporting_service, report_request)

    if not report_data:
        logger.info("No performance data returned from Bing Ads")
        return _empty_performance_result()

    # Parse and filter for our offer_id
    return _parse_product_report(report_data, offer_id)


def _build_product_performance_report(
    *,
    reporting_service,
    account_id: int,
    start_date: str,
    end_date: str,
):
    """Build ProductDimensionPerformanceReport request."""
    report_request = reporting_service.factory.create(
        "ProductDimensionPerformanceReportRequest"
    )

    report_request.Aggregation = "Daily"
    report_request.ExcludeColumnHeaders = False
    report_request.ExcludeReportFooter = True
    report_request.ExcludeReportHeader = True
    report_request.Format = "Csv"
    report_request.ReportName = "FeedOps Product Performance Report"
    report_request.ReturnOnlyCompleteData = False

    # Time period
    report_time = reporting_service.factory.create("ReportTime")
    report_time.CustomDateRangeStart = reporting_service.factory.create("Date")
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    report_time.CustomDateRangeStart.Day = start_dt.day
    report_time.CustomDateRangeStart.Month = start_dt.month
    report_time.CustomDateRangeStart.Year = start_dt.year

    report_time.CustomDateRangeEnd = reporting_service.factory.create("Date")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    report_time.CustomDateRangeEnd.Day = end_dt.day
    report_time.CustomDateRangeEnd.Month = end_dt.month
    report_time.CustomDateRangeEnd.Year = end_dt.year

    report_request.Time = report_time

    # Scope - specific account
    scope = reporting_service.factory.create("AccountThroughAdGroupReportScope")
    scope.AccountIds = {"long": [account_id]}
    scope.Campaigns = None
    scope.AdGroups = None
    report_request.Scope = scope

    # Columns to retrieve
    columns = reporting_service.factory.create(
        "ArrayOfProductDimensionPerformanceReportColumn"
    )
    columns.ProductDimensionPerformanceReportColumn.append("TimePeriod")
    columns.ProductDimensionPerformanceReportColumn.append("MerchantProductId")
    columns.ProductDimensionPerformanceReportColumn.append("Title")
    columns.ProductDimensionPerformanceReportColumn.append("Impressions")
    columns.ProductDimensionPerformanceReportColumn.append("Clicks")
    columns.ProductDimensionPerformanceReportColumn.append("Ctr")
    columns.ProductDimensionPerformanceReportColumn.append("Conversions")
    columns.ProductDimensionPerformanceReportColumn.append("Revenue")
    columns.ProductDimensionPerformanceReportColumn.append("Spend")

    report_request.Columns = columns

    return report_request


def _download_report(reporting_service, report_request) -> str | None:
    """Submit report request and download results."""
    from bingads.v13.reporting import (  # type: ignore[import-not-found]
        ReportingDownloadParameters,
        ReportingServiceManager,
    )

    # Submit the report request
    try:
        report_request_response = reporting_service.SubmitGenerateReport(
            ReportRequest=report_request
        )
        report_request_id = report_request_response.ReportRequestId
    except Exception as e:
        logger.error("Failed to submit Bing report request: %s", e)
        return None

    # Poll for completion
    max_polls = 60  # 5 minutes max
    poll_interval = 5  # seconds

    for _ in range(max_polls):
        try:
            poll_response = reporting_service.PollGenerateReport(
                ReportRequestId=report_request_id
            )
            status = poll_response.Status

            if status == "Success":
                # Download the report
                if poll_response.ReportDownloadUrl:
                    import httpx

                    with httpx.Client(timeout=60.0) as client:
                        response = client.get(poll_response.ReportDownloadUrl)
                        response.raise_for_status()
                        return response.text
                return None

            elif status == "Error":
                logger.error("Bing report generation failed")
                return None

            # Still pending, wait and poll again
            time.sleep(poll_interval)

        except Exception as e:
            logger.error("Failed to poll Bing report status: %s", e)
            return None

    logger.error("Bing report generation timed out")
    return None


def _parse_product_report(
    report_data: str,
    target_offer_id: str,
) -> dict[str, Any]:
    """Parse CSV report data and filter for target offer ID."""
    reader = csv.DictReader(StringIO(report_data))

    total_impressions = 0
    total_clicks = 0
    total_conversions = 0.0
    total_revenue = 0.0
    total_spend = 0.0
    daily_data: list[dict] = []

    target_lower = target_offer_id.lower()

    for row in reader:
        # Check if this row matches our offer ID
        merchant_product_id = row.get("MerchantProductId", "")
        if merchant_product_id.lower() != target_lower:
            continue

        impressions = int(row.get("Impressions", 0) or 0)
        clicks = int(row.get("Clicks", 0) or 0)
        ctr_str = row.get("Ctr", "0").replace("%", "")
        ctr = float(ctr_str) / 100 if ctr_str else 0.0
        conversions = float(row.get("Conversions", 0) or 0)
        revenue = float(row.get("Revenue", 0) or 0)
        spend = float(row.get("Spend", 0) or 0)

        total_impressions += impressions
        total_clicks += clicks
        total_conversions += conversions
        total_revenue += revenue
        total_spend += spend

        daily_roas = revenue / spend if spend > 0 else 0.0

        daily_data.append(
            {
                "date": row.get("TimePeriod", ""),
                "impressions": impressions,
                "clicks": clicks,
                "ctr": ctr,
                "conversions": int(conversions),
                "conversion_value": revenue,
                "cost": spend,
                "roas": daily_roas,
            }
        )

    if total_impressions == 0:
        return _empty_performance_result()

    # Calculate aggregate metrics
    ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    roas = total_revenue / total_spend if total_spend > 0 else 0.0

    return {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "ctr": ctr,
        "conversions": int(total_conversions),
        "conversion_value": total_revenue,
        "cost": total_spend,
        "roas": roas,
        "daily_data": daily_data,
    }


def fetch_batch_bing_performance(
    offer_ids: list[str],
    start_date: str,
    end_date: str,
    *,
    customer_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch performance metrics for multiple products.

    More efficient than individual calls as it downloads one report
    containing all products.

    Args:
        offer_ids: List of product offer IDs.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        customer_id: Bing Ads customer ID.
        account_id: Bing Ads account ID.

    Returns:
        Dictionary mapping offer_id to performance metrics.
    """
    customer_id = customer_id or _truthy_env("BING_ADS_CUSTOMER_ID")
    account_id = account_id or _truthy_env("BING_ADS_ACCOUNT_ID")

    if not _api_enabled():
        logger.warning("Bing Ads API is not enabled for batch performance fetch.")
        return {oid: _empty_performance_result() for oid in offer_ids}

    if not customer_id or not account_id:
        raise ValueError("BING_ADS_CUSTOMER_ID and BING_ADS_ACCOUNT_ID are required.")

    if not offer_ids:
        return {}

    try:
        return _fetch_batch_performance_via_api(
            offer_ids=offer_ids,
            start_date=start_date,
            end_date=end_date,
            customer_id=customer_id,
            account_id=account_id,
        )
    except ImportError as e:
        logger.error("bingads SDK not installed")
        raise ValueError("bingads SDK required") from e
    except Exception as e:
        logger.error("Failed to fetch batch Bing performance: %s", e)
        raise ValueError(f"Failed to fetch batch Bing performance: {e}") from e


def _fetch_batch_performance_via_api(
    *,
    offer_ids: list[str],
    start_date: str,
    end_date: str,
    customer_id: str,
    account_id: str,
) -> dict[str, dict[str, Any]]:
    """Fetch batch performance metrics using Bing Ads Reporting API."""
    from bingads.service_client import ServiceClient  # type: ignore[import-not-found]

    authorization_data = _get_authorization_data()

    if customer_id:
        authorization_data.customer_id = customer_id
    if account_id:
        authorization_data.account_id = account_id

    reporting_service = ServiceClient(
        service="ReportingService",
        version=13,
        authorization_data=authorization_data,
        environment="production",
    )

    # Build report (same as single fetch, but we parse all results)
    report_request = _build_product_performance_report(
        reporting_service=reporting_service,
        account_id=int(account_id),
        start_date=start_date,
        end_date=end_date,
    )

    report_data = _download_report(reporting_service, report_request)

    if not report_data:
        return {oid: _empty_performance_result() for oid in offer_ids}

    # Parse all products from report
    return _parse_batch_product_report(report_data, offer_ids)


def _parse_batch_product_report(
    report_data: str,
    target_offer_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Parse CSV report data for multiple offer IDs."""
    reader = csv.DictReader(StringIO(report_data))

    # Normalize target IDs for matching
    target_set = {oid.lower() for oid in target_offer_ids}

    # Group by offer ID
    grouped: dict[str, list[dict]] = defaultdict(list)

    for row in reader:
        merchant_product_id = row.get("MerchantProductId", "")
        if merchant_product_id.lower() in target_set:
            grouped[merchant_product_id].append(row)

    # Aggregate each product
    results: dict[str, dict[str, Any]] = {}

    for offer_id in target_offer_ids:
        rows = grouped.get(offer_id, [])

        if not rows:
            # Also try case-insensitive match
            for key, val in grouped.items():
                if key.lower() == offer_id.lower():
                    rows = val
                    break

        if not rows:
            results[offer_id] = _empty_performance_result()
            continue

        total_impressions = 0
        total_clicks = 0
        total_conversions = 0.0
        total_revenue = 0.0
        total_spend = 0.0
        daily_data: list[dict] = []

        for row in rows:
            impressions = int(row.get("Impressions", 0) or 0)
            clicks = int(row.get("Clicks", 0) or 0)
            ctr_str = row.get("Ctr", "0").replace("%", "")
            ctr = float(ctr_str) / 100 if ctr_str else 0.0
            conversions = float(row.get("Conversions", 0) or 0)
            revenue = float(row.get("Revenue", 0) or 0)
            spend = float(row.get("Spend", 0) or 0)

            total_impressions += impressions
            total_clicks += clicks
            total_conversions += conversions
            total_revenue += revenue
            total_spend += spend

            daily_roas = revenue / spend if spend > 0 else 0.0

            daily_data.append(
                {
                    "date": row.get("TimePeriod", ""),
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr": ctr,
                    "conversions": int(conversions),
                    "conversion_value": revenue,
                    "cost": spend,
                    "roas": daily_roas,
                }
            )

        ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        roas = total_revenue / total_spend if total_spend > 0 else 0.0

        results[offer_id] = {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "ctr": ctr,
            "conversions": int(total_conversions),
            "conversion_value": total_revenue,
            "cost": total_spend,
            "roas": roas,
            "daily_data": daily_data,
        }

    return results
