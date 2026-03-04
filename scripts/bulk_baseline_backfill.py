#!/usr/bin/env python3
"""Bulk baseline backfill — capture 30-day Google Ads performance baselines for all SKUs.

This script captures performance baselines for all master SKUs in variant_index,
writing to both performance_baselines (master level) and performance_baselines_variant
(per-offer-ID level).

Quota calculation:
- ~2,500 master SKUs x ~28 variants = ~70,000 offer IDs
- fetch_batch_product_performance() chunks at 25 offer IDs per GAQL request
- ~70,000 / 25 = ~2,800 GAQL requests total
- Daily quota: 14,400 requests/day — this sweep consumes ~19%
- 50-SKU test gate: ~50 x 28 / 25 = ~56 GAQL requests (safe)

Processing order: Published SKUs first (have entries in publish_events),
then remaining master_skus in alphabetical order.

Zero baselines: SKUs with no Google Ads data receive an explicit zero-baseline
record with metadata {"zero_baseline": true, "reason": "no_google_ads_data"}.
This prevents repeated API calls for known-zero SKUs.

Usage:
    # MANDATORY: Run test gate first to validate data quality before full sweep
    PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --test-gate

    # Dry run — list SKUs in processing order without calling the API
    PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --dry-run

    # Full sweep (only after test gate has been reviewed and approved)
    PYTHONPATH=./src python scripts/bulk_baseline_backfill.py

    # Custom batch size and sleep interval
    PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --batch-size 25 --sleep 3.0

Environment:
    Loads credentials from .env.vercel (standard pattern for scripts/).
    Required: SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
              GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_DEVELOPER_TOKEN (etc.)
    Optional: GOOGLE_ADS_API_ENABLED=1 (must be set to actually call the API)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Allow running with PYTHONPATH=./src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from feedops.api.performance_baseline import _capture_google_baseline
from feedops.db.supabase_client import get_client
from feedops.utils.offer_id import normalize_offer_id

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 50
DEFAULT_SLEEP_BETWEEN_BATCHES = 2.0  # seconds
TEST_GATE_SKU_LIMIT = 50
DAYS_LOOKBACK = 30


# ---------------------------------------------------------------------------
# SKU Priority Ordering
# ---------------------------------------------------------------------------


def get_published_master_skus(supabase) -> list[str]:
    """Return master_skus that have at least one publish event (priority group)."""
    result = (
        supabase.table("publish_events")
        .select("master_sku")
        .execute()
    )
    # De-duplicate while preserving order from the DB (latest first)
    seen: set[str] = set()
    ordered: list[str] = []
    for row in result.data or []:
        sku = row.get("master_sku")
        if sku and sku not in seen:
            seen.add(sku)
            ordered.append(sku)
    return ordered


def get_all_master_skus(supabase) -> list[str]:
    """Return all distinct master_skus from variant_index, sorted alphabetically."""
    result = (
        supabase.table("variant_index")
        .select("master_sku")
        .execute()
    )
    skus = {row["master_sku"] for row in result.data or [] if row.get("master_sku")}
    return sorted(skus)


def build_ordered_sku_list(supabase) -> list[str]:
    """Build priority-ordered SKU list: published first, then remaining alphabetically."""
    published = get_published_master_skus(supabase)
    published_set = set(published)
    all_skus = get_all_master_skus(supabase)
    remaining = [s for s in all_skus if s not in published_set]
    return published + remaining


# ---------------------------------------------------------------------------
# Variant Lookup
# ---------------------------------------------------------------------------


def get_offer_ids_for_sku(supabase, master_sku: str) -> list[str]:
    """Return all normalized offer IDs for a master SKU from variant_index."""
    result = (
        supabase.table("variant_index")
        .select("gmc_offer_id")
        .eq("master_sku", master_sku)
        .execute()
    )
    offer_ids = []
    for row in result.data or []:
        raw = row.get("gmc_offer_id")
        if raw:
            normalized = normalize_offer_id(raw)
            if normalized:
                offer_ids.append(normalized)
    return offer_ids


# ---------------------------------------------------------------------------
# Zero Baseline Storage
# ---------------------------------------------------------------------------


def store_zero_baseline(supabase, master_sku: str, start_date: str, end_date: str) -> None:
    """Store an explicit zero-baseline record for a SKU with no Google Ads data.

    Uses metadata JSONB column to flag as zero-baseline so repeated API calls
    can be skipped for known-zero SKUs.
    """
    zero_data: dict[str, Any] = {
        "master_sku": master_sku,
        "platform": "google",
        "avg_impressions": 0.0,
        "avg_clicks": 0.0,
        "avg_ctr": 0.0,
        "avg_conversions": 0.0,
        "avg_cvr": 0.0,
        "avg_cost": 0.0,
        "avg_roas": 0.0,
        "baseline_start_date": start_date,
        "baseline_end_date": end_date,
    }
    # Include metadata if the column exists (migration 030 added it)
    try:
        zero_data["metadata"] = '{"zero_baseline": true, "reason": "no_google_ads_data"}'
        supabase.table("performance_baselines").upsert(
            zero_data,
            on_conflict="master_sku,platform",
        ).execute()
    except Exception:
        # Retry without metadata in case column doesn't exist
        zero_data.pop("metadata", None)
        supabase.table("performance_baselines").upsert(
            zero_data,
            on_conflict="master_sku,platform",
        ).execute()


def store_variant_zero_baselines(
    supabase,
    master_sku: str,
    offer_ids: list[str],
    start_date: str,
    end_date: str,
) -> int:
    """Store zero-baseline records for each offer ID when no data returned."""
    stored = 0
    for offer_id in offer_ids:
        try:
            supabase.table("performance_baselines_variant").upsert(
                {
                    "gmc_offer_id": offer_id,
                    "master_sku": master_sku,
                    "platform": "google",
                    "baseline_start_date": start_date,
                    "baseline_end_date": end_date,
                    "avg_impressions": 0.0,
                    "avg_clicks": 0.0,
                    "avg_ctr": 0.0,
                    "avg_conversions": 0.0,
                    "avg_cvr": 0.0,
                    "avg_cost": 0.0,
                    "avg_roas": 0.0,
                },
                on_conflict="gmc_offer_id,platform",
            ).execute()
            stored += 1
        except Exception as e:
            logger.warning("Failed to store zero variant baseline for %s/%s: %s", master_sku, offer_id, e)
    return stored


# ---------------------------------------------------------------------------
# Variant-Level Baseline Capture
# ---------------------------------------------------------------------------


def capture_variant_baselines(
    supabase,
    master_sku: str,
    offer_ids: list[str],
    start_date: str,
    end_date: str,
) -> tuple[int, int]:
    """Capture per-offer-ID baselines for a master SKU.

    Fetches Google Ads data for each offer ID individually and stores per-variant
    aggregates in performance_baselines_variant.

    Returns:
        Tuple of (variants_with_data, variants_stored).
    """
    from feedops.integrations.google_ads_performance import fetch_batch_product_performance

    if not offer_ids:
        return 0, 0

    # Fetch all offer IDs in one batch call (already chunked inside the function)
    try:
        performance_data = fetch_batch_product_performance(
            offer_ids=offer_ids,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        logger.error("Failed to fetch batch performance for %s: %s", master_sku, e)
        return 0, 0

    if not performance_data:
        return 0, 0

    days_lookback = (
        datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")
    ).days or 1

    variants_with_data = 0
    variants_stored = 0

    for offer_id in offer_ids:
        normalized_id = normalize_offer_id(offer_id) or offer_id
        # performance_data keys may be unnormalized (uppercase from API)
        metrics = performance_data.get(normalized_id) or performance_data.get(
            offer_id.upper() if offer_id else offer_id
        )

        # Try both cases since fetch_batch_product_performance normalizes internally
        if not metrics:
            # Check all keys case-insensitively
            for key, val in performance_data.items():
                if normalize_offer_id(key) == normalized_id:
                    metrics = val
                    break

        if not metrics or metrics.get("impressions", 0) == 0:
            continue

        variants_with_data += 1
        total_impressions = int(metrics.get("impressions", 0))
        total_clicks = int(metrics.get("clicks", 0))
        total_conversions = float(metrics.get("conversions", 0))
        total_conversion_value = float(metrics.get("conversion_value", 0.0))
        total_cost = float(metrics.get("cost", 0.0))

        avg_impressions = total_impressions / days_lookback
        avg_clicks = total_clicks / days_lookback
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        avg_conversions = total_conversions / days_lookback
        avg_conversion_value = total_conversion_value / days_lookback
        avg_cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0
        avg_cost = total_cost / days_lookback
        avg_roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

        try:
            supabase.table("performance_baselines_variant").upsert(
                {
                    "gmc_offer_id": normalized_id,
                    "master_sku": master_sku,
                    "platform": "google",
                    "baseline_start_date": start_date,
                    "baseline_end_date": end_date,
                    "avg_impressions": round(avg_impressions, 2),
                    "avg_clicks": round(avg_clicks, 4),
                    "avg_ctr": round(avg_ctr, 6),
                    "avg_conversions": round(avg_conversions, 4),
                    "avg_conversion_value": round(avg_conversion_value, 4),
                    "avg_cvr": round(avg_cvr, 6),
                    "avg_cost": round(avg_cost, 4),
                    "avg_roas": round(avg_roas, 4),
                },
                on_conflict="gmc_offer_id,platform",
            ).execute()
            variants_stored += 1
        except Exception as e:
            logger.warning(
                "Failed to store variant baseline for %s/%s: %s", master_sku, normalized_id, e
            )

    return variants_with_data, variants_stored


# ---------------------------------------------------------------------------
# Single SKU Processing
# ---------------------------------------------------------------------------


def process_sku(
    supabase,
    master_sku: str,
    start_date: str,
    end_date: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Process a single master SKU: capture master baseline + variant baselines.

    Returns:
        Result dict with keys: success, has_data, offer_ids_found,
        variants_with_data, variants_stored, error.
    """
    result: dict[str, Any] = {
        "master_sku": master_sku,
        "success": False,
        "has_data": False,
        "offer_ids_found": 0,
        "variants_with_data": 0,
        "variants_stored": 0,
        "error": None,
    }

    if dry_run:
        result["success"] = True
        return result

    offer_ids = get_offer_ids_for_sku(supabase, master_sku)
    result["offer_ids_found"] = len(offer_ids)

    if not offer_ids:
        logger.warning("%s: No offer IDs found in variant_index — skipping", master_sku)
        result["error"] = "no_offer_ids"
        return result

    try:
        # Capture master-level baseline
        baseline_metrics = _capture_google_baseline(
            supabase=supabase,
            master_sku=master_sku,
            offer_ids=offer_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if baseline_metrics and baseline_metrics.get("avg_impressions", 0) > 0:
            result["has_data"] = True
        else:
            # Store explicit zero baseline
            store_zero_baseline(supabase, master_sku, start_date, end_date)

        # Capture variant-level baselines
        variants_with_data, variants_stored = capture_variant_baselines(
            supabase, master_sku, offer_ids, start_date, end_date
        )
        result["variants_with_data"] = variants_with_data
        result["variants_stored"] = variants_stored

        # Store zero-variant baselines for offer IDs with no data
        if variants_with_data < len(offer_ids):
            no_data_ids = offer_ids  # store_variant_zero_baselines handles upsert
            store_variant_zero_baselines(supabase, master_sku, no_data_ids, start_date, end_date)

        result["success"] = True

    except Exception as e:
        logger.error("%s: Processing failed — %s", master_sku, e)
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------


def process_batch(
    supabase,
    skus: list[str],
    start_date: str,
    end_date: str,
    batch_num: int,
    total_batches: int,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Process a single batch of SKUs and return results."""
    batch_results = []
    batch_start = time.monotonic()

    for master_sku in skus:
        sku_result = process_sku(supabase, master_sku, start_date, end_date, dry_run=dry_run)
        batch_results.append(sku_result)

    elapsed = time.monotonic() - batch_start
    skus_with_data = sum(1 for r in batch_results if r["has_data"])
    total_variants_stored = sum(r["variants_stored"] for r in batch_results)
    errors = [r for r in batch_results if r["error"]]

    logger.info(
        "Batch %d/%d — %d SKUs | %d with data | %d variant rows stored | %.1fs | %d errors",
        batch_num,
        total_batches,
        len(skus),
        skus_with_data,
        total_variants_stored,
        elapsed,
        len(errors),
    )

    return batch_results


# ---------------------------------------------------------------------------
# Test Gate Summary
# ---------------------------------------------------------------------------


def print_test_gate_summary(
    results: list[dict[str, Any]],
    elapsed_seconds: float,
    dry_run: bool,
) -> None:
    """Print a structured test gate summary for human review."""
    total = len(results)
    succeeded = sum(1 for r in results if r["success"])
    with_data = sum(1 for r in results if r["has_data"])
    total_offer_ids = sum(r["offer_ids_found"] for r in results)
    total_variants_stored = sum(r["variants_stored"] for r in results)
    errors = [r for r in results if r["error"]]

    match_rate = (with_data / total * 100) if total > 0 else 0.0
    seconds_per_sku = elapsed_seconds / total if total > 0 else 0.0

    print("\n" + "=" * 60)
    print("TEST GATE SUMMARY")
    print("=" * 60)
    print(f"SKUs tested:            {total}")
    print(f"Successfully processed: {succeeded}")
    print(f"SKUs with GA data:      {with_data}")
    print(f"Offer ID match rate:    {match_rate:.1f}%  (target: >90%)")
    print(f"Total offer IDs:        {total_offer_ids}")
    print(f"Variant baselines:      {total_variants_stored} rows stored")
    print(f"Elapsed time:           {elapsed_seconds:.1f}s")
    print(f"Time per SKU:           {seconds_per_sku:.2f}s")
    if dry_run:
        print("Mode:                   DRY RUN (no API calls)")
    print()

    if errors:
        print(f"Errors ({len(errors)}):")
        for r in errors[:10]:
            print(f"  {r['master_sku']}: {r['error']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        print()

    if match_rate >= 90 and not dry_run:
        print("RESULT: TEST GATE PASSED — safe to run full sweep")
        print("Run:  PYTHONPATH=./src python scripts/bulk_baseline_backfill.py")
    elif dry_run:
        print("RESULT: DRY RUN — no API calls made, SKU list shown above")
    else:
        print("RESULT: TEST GATE FAILED — match rate below 90%")
        print("Check: offer ID format in variant_index, Google Ads API connectivity")
    print("=" * 60)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bulk Google Ads baseline backfill for all master SKUs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # MANDATORY: Run test gate first
  PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --test-gate

  # Dry run (list SKUs, no API calls)
  PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --dry-run

  # Full sweep (only after test gate approved)
  PYTHONPATH=./src python scripts/bulk_baseline_backfill.py

  # Custom throttling
  PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --batch-size 25 --sleep 3.0
        """,
    )
    parser.add_argument(
        "--test-gate",
        action="store_true",
        help=f"Process only first {TEST_GATE_SKU_LIMIT} SKUs, print quality summary.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List all SKUs in processing order without calling the Google Ads API.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        metavar="N",
        help=f"SKUs per batch before sleeping (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_BETWEEN_BATCHES,
        metavar="SECONDS",
        help=f"Seconds to sleep between batches (default: {DEFAULT_SLEEP_BETWEEN_BATCHES}).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_LOOKBACK,
        metavar="DAYS",
        help=f"Days of lookback for baseline period (default: {DAYS_LOOKBACK}).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Date range: last N days ending yesterday
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=args.days)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    logger.info("Bulk baseline backfill — %s to %s (%d days)", start_str, end_str, args.days)

    supabase = get_client()

    logger.info("Building SKU priority list (published first)...")
    ordered_skus = build_ordered_sku_list(supabase)
    total_skus = len(ordered_skus)
    logger.info("Total SKUs: %d", total_skus)

    # Apply limits
    if args.test_gate:
        skus_to_process = ordered_skus[:TEST_GATE_SKU_LIMIT]
        logger.info("TEST GATE MODE — processing first %d SKUs", len(skus_to_process))
    else:
        skus_to_process = ordered_skus

    if args.dry_run:
        logger.info("DRY RUN — listing SKUs (no API calls)")
        print(f"\nProcessing order ({len(skus_to_process)} SKUs):")
        for i, sku in enumerate(skus_to_process, 1):
            print(f"  {i:4d}. {sku}")
        if not args.test_gate:
            print(f"\n  ... total {total_skus} SKUs would be processed in full sweep")
        return 0

    # Split into batches
    batch_size = max(1, args.batch_size)
    batches = [
        skus_to_process[i : i + batch_size]
        for i in range(0, len(skus_to_process), batch_size)
    ]
    total_batches = len(batches)

    logger.info(
        "Processing %d SKUs in %d batches of up to %d (sleep %.1fs between batches)",
        len(skus_to_process),
        total_batches,
        batch_size,
        args.sleep,
    )

    all_results: list[dict[str, Any]] = []
    sweep_start = time.monotonic()

    for batch_idx, batch_skus in enumerate(batches, 1):
        batch_results = process_batch(
            supabase=supabase,
            skus=batch_skus,
            start_date=start_str,
            end_date=end_str,
            batch_num=batch_idx,
            total_batches=total_batches,
            dry_run=args.dry_run,
        )
        all_results.extend(batch_results)

        # Sleep between batches (not after the last one)
        if batch_idx < total_batches and args.sleep > 0:
            time.sleep(args.sleep)

    total_elapsed = time.monotonic() - sweep_start

    # Print summary
    if args.test_gate:
        print_test_gate_summary(all_results, total_elapsed, dry_run=args.dry_run)
    else:
        # Full sweep summary
        total = len(all_results)
        succeeded = sum(1 for r in all_results if r["success"])
        with_data = sum(1 for r in all_results if r["has_data"])
        total_variants_stored = sum(r["variants_stored"] for r in all_results)
        errors = [r for r in all_results if r["error"]]

        print("\n" + "=" * 60)
        print("FULL SWEEP COMPLETE")
        print("=" * 60)
        print(f"SKUs processed:         {total}")
        print(f"Successful:             {succeeded}")
        print(f"With GA data:           {with_data}")
        print(f"Zero baselines:         {total - with_data}")
        print(f"Variant baselines:      {total_variants_stored} rows stored")
        print(f"Errors:                 {len(errors)}")
        print(f"Total elapsed:          {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
        if total > 0:
            print(f"Time per SKU:           {total_elapsed/total:.2f}s")
        print("=" * 60)

        if errors:
            logger.warning("Failed SKUs (%d):", len(errors))
            for r in errors[:20]:
                logger.warning("  %s: %s", r["master_sku"], r["error"])

    error_count = sum(1 for r in all_results if r["error"])
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
