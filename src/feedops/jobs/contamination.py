"""Publish event contamination prevention for baseline capture.

Prevents capturing baseline metrics for SKUs that were published within the
contamination window (default 30 days). Publishing content creates a discontinuity
in performance data, so baselines must be captured from pre-optimization periods only.

This ensures baseline vs. post-publish comparisons are measuring the impact of
content changes, not mixing pre/post data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from feedops.db.supabase_client import get_client

logger = logging.getLogger(__name__)

# Validation threshold: SKUs published within this many days are ineligible for baseline capture
BASELINE_CONTAMINATION_DAYS = 30


def check_baseline_eligibility(
    master_sku: str,
    platform: str = "google"
) -> tuple[bool, str]:
    """Check if a SKU is eligible for baseline capture.

    A SKU is ineligible if it was successfully published within the last
    BASELINE_CONTAMINATION_DAYS days, as this would mix pre/post-optimization data.

    Args:
        master_sku: Master SKU ID to check
        platform: Platform to check ("google" or "bing")

    Returns:
        Tuple of (eligible: bool, reason: str)
        - (True, "Eligible for baseline capture") if no recent publish
        - (False, "Published N days ago (< 30 day threshold)") if recently published

    Notes:
        - Queries publish_events for status='success' publishes
        - Only considers the specified platform
        - Returns eligible if no publish events found
    """
    supabase = get_client()

    # Calculate threshold date
    threshold = datetime.now(timezone.utc) - timedelta(days=BASELINE_CONTAMINATION_DAYS)

    # Query for recent successful publishes
    result = supabase.table("publish_events").select(
        "published_at"
    ).eq("master_sku", master_sku).eq(
        "platform", platform
    ).eq("status", "success").gte(
        "published_at", threshold.isoformat()
    ).order(
        "published_at", desc=True
    ).limit(1).execute()

    if not result.data:
        return (True, "Eligible for baseline capture")

    # Found a recent publish event
    published_at = datetime.fromisoformat(result.data[0]["published_at"].replace("Z", "+00:00"))
    days_ago = (datetime.now(timezone.utc) - published_at).days

    return (
        False,
        f"Published {days_ago} days ago (< {BASELINE_CONTAMINATION_DAYS} day threshold)"
    )


def check_batch_eligibility(
    master_skus: list[str],
    platform: str = "google"
) -> dict[str, tuple[bool, str]]:
    """Check baseline eligibility for a batch of SKUs.

    More efficient than calling check_baseline_eligibility repeatedly,
    as it uses a single database query for the entire batch.

    Args:
        master_skus: List of master SKU IDs to check
        platform: Platform to check ("google" or "bing")

    Returns:
        Dict mapping master_sku -> (eligible: bool, reason: str)
        Example: {
            "WP-2/16-GAL": (True, "Eligible for baseline capture"),
            "DMF-2/2X": (False, "Published 15 days ago (< 30 day threshold)")
        }

    Notes:
        - Performs single query for efficiency
        - Returns eligible status for ALL SKUs in batch
        - SKUs without publish events are marked eligible
    """
    if not master_skus:
        return {}

    supabase = get_client()

    # Calculate threshold date
    threshold = datetime.now(timezone.utc) - timedelta(days=BASELINE_CONTAMINATION_DAYS)

    # Query for recent successful publishes for all SKUs in batch
    result = supabase.table("publish_events").select(
        "master_sku, published_at"
    ).in_("master_sku", master_skus).eq(
        "platform", platform
    ).eq("status", "success").gte(
        "published_at", threshold.isoformat()
    ).order(
        "published_at", desc=True
    ).execute()

    # Build map of SKU -> most recent publish date
    recent_publishes: dict[str, datetime] = {}
    for row in result.data:
        sku = row["master_sku"]
        published_at = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
        # Keep only the most recent publish for each SKU
        if sku not in recent_publishes or published_at > recent_publishes[sku]:
            recent_publishes[sku] = published_at

    # Build eligibility status for each SKU
    eligibility: dict[str, tuple[bool, str]] = {}
    for sku in master_skus:
        if sku in recent_publishes:
            days_ago = (datetime.now(timezone.utc) - recent_publishes[sku]).days
            eligibility[sku] = (
                False,
                f"Published {days_ago} days ago (< {BASELINE_CONTAMINATION_DAYS} day threshold)"
            )
        else:
            eligibility[sku] = (True, "Eligible for baseline capture")

    logger.info(
        f"Batch eligibility check: {len([e for e in eligibility.values() if e[0]])} eligible, "
        f"{len([e for e in eligibility.values() if not e[0]])} ineligible"
    )

    return eligibility


def validate_date_boundaries(
    baseline_start: str,
    baseline_end: str,
    master_sku: str,
    platform: str = "google"
) -> tuple[bool, str]:
    """Validate that baseline date range doesn't overlap with publish events.

    Even if a SKU passed the contamination threshold check, we should verify
    that the specific baseline capture period doesn't overlap with any publish.

    Args:
        baseline_start: Start date in YYYY-MM-DD format
        baseline_end: End date in YYYY-MM-DD format
        master_sku: Master SKU ID to check
        platform: Platform to check ("google" or "bing")

    Returns:
        Tuple of (valid: bool, message: str)
        - (True, "No publish events in baseline period") if clean
        - (False, "Baseline period overlaps publish event at YYYY-MM-DD") if overlap

    Notes:
        - Checks for ANY successful publish within the date range
        - Used as additional validation after contamination threshold check
        - Prevents edge cases where baseline window spans a publish
    """
    supabase = get_client()

    # Query for any successful publish within the baseline period
    result = supabase.table("publish_events").select(
        "published_at"
    ).eq("master_sku", master_sku).eq(
        "platform", platform
    ).eq("status", "success").gte(
        "published_at", baseline_start
    ).lte(
        "published_at", baseline_end
    ).limit(1).execute()

    if result.data:
        published_at = result.data[0]["published_at"][:10]  # Extract date portion
        return (
            False,
            f"Baseline period overlaps publish event at {published_at}"
        )

    return (True, "No publish events in baseline period")
