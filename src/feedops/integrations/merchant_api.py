"""Merchant Reports API client for querying product approval status.

Queries the GMC Merchant Reports API (product_view) for disapproved and
limited products, normalizing offer IDs to lowercase for Supabase consistency.

CRITICAL: Merchant API returns offer IDs in uppercase (shopify_US_...) but
our database stores them lowercase (shopify_us_...). This module normalizes
to lowercase on all outputs.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

MAPI_SCOPE = "https://www.googleapis.com/auth/content"
MAPI_REPORTS_URL = (
    "https://merchantapi.googleapis.com/reports/v1beta/accounts/{mc_id}/reports:search"
)


def _get_access_token() -> str:
    """Obtain an OAuth2 access token via service account credentials.

    Reuses the credential loading logic from merchant_center.py, reading
    from the same environment variables (GOOGLE_APPLICATION_CREDENTIALS,
    GOOGLE_SERVICE_ACCOUNT_KEY, etc.).
    """
    import base64
    import binascii
    import json

    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    env = os.environ
    gac = (env.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if gac:
        from pathlib import Path
        gac_path = Path(gac).expanduser()
        if gac_path.exists():
            creds = service_account.Credentials.from_service_account_file(
                str(gac_path), scopes=[MAPI_SCOPE]
            )
            creds.refresh(Request())
            return creds.token

    gsa_key = (env.get("GOOGLE_SERVICE_ACCOUNT_KEY") or "").strip()
    if gsa_key:
        raw = gsa_key.strip()
        # Try raw JSON first
        if raw.startswith("{"):
            info = json.loads(raw)
        else:
            # Try base64
            compact = "".join(raw.split())
            try:
                decoded = base64.b64decode(compact, validate=True)
                info = json.loads(decoded.decode("utf-8").strip())
            except (binascii.Error, ValueError, json.JSONDecodeError):
                info = None
        if info:
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=[MAPI_SCOPE]
            )
            creds.refresh(Request())
            return creds.token

    # Fall back to google.auth.default() (works in Cloud Run with Workload Identity)
    import google.auth

    creds, _ = google.auth.default(scopes=[MAPI_SCOPE])
    creds.refresh(Request())
    return creds.token


class MerchantApiClient:
    """Client for the Merchant Reports API (product_view queries)."""

    def __init__(self, merchant_center_id: str | None = None) -> None:
        self.mc_id = (
            merchant_center_id
            or os.environ.get("GMC_MERCHANT_ID")
            or os.environ.get("FEEDOPS_MERCHANT_CENTER_ID")
        )
        if not self.mc_id:
            raise ValueError(
                "Merchant Center ID not set. "
                "Set GMC_MERCHANT_ID environment variable."
            )

    def _reports_url(self) -> str:
        return MAPI_REPORTS_URL.format(mc_id=self.mc_id)

    def _run_query(self, query: str) -> list[dict[str, Any]]:
        """Execute a Merchant Reports API query and return all result rows."""
        token = _get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = self._reports_url()
        results: list[dict[str, Any]] = []
        page_token: str | None = None

        with httpx.Client(timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=30.0)) as client:
            while True:
                payload: dict[str, Any] = {"query": query, "pageSize": 1000}
                if page_token:
                    payload["pageToken"] = page_token

                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

                rows = data.get("results", [])
                results.extend(rows)

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return results

    def query_disapproved_products(self) -> list[dict[str, Any]]:
        """Query product_view for all products with disapproval or limitation issues.

        Returns:
            List of product status dicts with normalized (lowercase) offer IDs,
            ready for upsert into gmc_product_status table.
        """
        query = (
            "SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues "
            "FROM product_view "
            "WHERE aggregated_reporting_context_status IN "
            "('NOT_ELIGIBLE_OR_DISAPPROVED', 'ELIGIBLE_LIMITED')"
        )

        try:
            rows = self._run_query(query)
        except httpx.HTTPStatusError as exc:
            logger.error("Merchant API query failed: %s %s", exc.response.status_code, exc.response.text[:500])
            raise

        products = []
        for row in rows:
            product_view = row.get("productView", {})
            offer_id_raw = product_view.get("offerId", "")
            # CRITICAL: Normalize to lowercase — Merchant API returns uppercase shopify_US_
            offer_id = offer_id_raw.lower()

            status_raw = product_view.get("aggregatedReportingContextStatus", "")
            status = _normalize_status(status_raw)

            item_issues_raw = product_view.get("itemIssues", [])
            parsed_issues = _parse_item_issues(item_issues_raw)
            disapproval_count = sum(
                1 for issue in parsed_issues
                if issue.get("severity") == "disapproval"
            )

            products.append({
                "gmc_offer_id": offer_id,
                "offer_title": product_view.get("title"),
                "status": status,
                "item_issues": parsed_issues,
                "issue_count": len(parsed_issues),
                "disapproval_count": disapproval_count,
            })

        logger.info(
            "Merchant API: fetched %d disapproved/limited products",
            len(products),
        )
        return products

    def query_all_product_statuses(self) -> list[dict[str, Any]]:
        """Query product_view for ALL products to get status counts.

        Returns:
            List of minimal product status dicts (offer_id + status only),
            for computing overall eligible/disapproved/limited counts.
        """
        query = (
            "SELECT offer_id, aggregated_reporting_context_status "
            "FROM product_view"
        )

        try:
            rows = self._run_query(query)
        except httpx.HTTPStatusError as exc:
            logger.error("Merchant API all-products query failed: %s", exc.response.status_code)
            raise

        products = []
        for row in rows:
            product_view = row.get("productView", {})
            offer_id_raw = product_view.get("offerId", "")
            offer_id = offer_id_raw.lower()  # Normalize to lowercase
            status_raw = product_view.get("aggregatedReportingContextStatus", "")
            products.append({
                "gmc_offer_id": offer_id,
                "status": _normalize_status(status_raw),
            })

        logger.info("Merchant API: fetched %d total product statuses", len(products))
        return products


def _normalize_status(status_raw: str) -> str:
    """Map GMC API status string to our simplified status."""
    mapping = {
        "NOT_ELIGIBLE_OR_DISAPPROVED": "disapproved",
        "ELIGIBLE_LIMITED": "limited",
        "ELIGIBLE": "approved",
        "PENDING": "pending",
    }
    return mapping.get(status_raw, "unknown")


def _parse_item_issues(item_issues_raw: list[dict]) -> list[dict[str, Any]]:
    """Parse GMC itemIssues array into structured dicts for storage."""
    parsed = []
    for issue in item_issues_raw:
        issue_type = issue.get("issueType", {})
        severity_info = issue.get("severity", {})

        parsed.append({
            "code": issue_type.get("code", ""),
            "canonical_attribute": issue_type.get("canonicalAttribute", ""),
            "severity": _normalize_severity(
                severity_info.get("aggregatedSeverity", "")
            ),
            "resolution": issue.get("resolution", ""),
            "applicable_contexts": [
                ctx.get("reportingContext", "")
                for ctx in issue.get("applicableContexts", [])
            ],
        })
    return parsed


def _normalize_severity(severity_raw: str) -> str:
    """Map GMC severity to simplified label."""
    mapping = {
        "DISAPPROVED": "disapproval",
        "DEMOTED": "demotion",
        "UNAFFECTED": "warning",
    }
    return mapping.get(severity_raw, severity_raw.lower() if severity_raw else "unknown")
