"""Quality reporting functions for data collection validation.

Provides completeness validation (VALID-01, VALID-07), freshness monitoring (VALID-02),
and statistical outlier detection (VALID-10) for backfill jobs and collected data.

Functions:
- validate_job_completeness: Check if all items in a job were processed successfully
- correct_job_status: Fix job status mismatches (enforce 95% threshold)
- get_freshness_report: Monitor data staleness across baselines, search terms, keywords
- detect_metric_outliers: Flag anomalous performance metrics using Z-scores
- generate_full_quality_report: Combined report for all validation checks
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from feedops.db.supabase_client import get_client
from feedops.jobs.manager import get_job, update_job_status
from feedops.jobs.validators import VALIDATION_THRESHOLDS

logger = logging.getLogger(__name__)

# Optional imports for statistical outlier detection
try:
    import numpy as np
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not installed - outlier detection will be unavailable")


def validate_job_completeness(job_id: str) -> dict[str, Any]:
    """Validate that a job has processed all items and calculate success metrics.

    Implements:
    - VALID-01: Verify 100% SKU coverage (all items accounted for)
    - VALID-07: Determine expected status based on 95% success threshold

    Args:
        job_id: UUID of the backfill job

    Returns:
        Dictionary with completeness metrics:
        {
            "job_id": str,
            "valid": bool,  # all items accounted for AND success >= 95%
            "total_items": int,
            "completed_items": int,
            "failed_items": int,
            "unaccounted_items": int,  # total - completed - failed
            "coverage_pct": float,
            "success_rate": float,
            "expected_status": str,  # what status should be
            "actual_status": str,
            "status_correct": bool,  # actual matches expected
        }

    Notes:
        - coverage_pct = (completed + failed) / total * 100
        - success_rate = completed / total * 100
        - expected_status: 'complete' if success >= 95%, 'partial' if 0% < success < 95%, 'failed' if 0%
    """
    job = get_job(job_id)

    if not job:
        return {
            "job_id": job_id,
            "valid": False,
            "error": "Job not found",
        }

    total = job.total_items
    completed = job.completed_items
    failed = job.failed_items

    # Calculate metrics
    unaccounted = total - completed - failed
    coverage_pct = ((completed + failed) / total * 100) if total > 0 else 0.0
    success_rate = (completed / total * 100) if total > 0 else 0.0

    # Determine expected status based on success rate
    success_threshold = VALIDATION_THRESHOLDS["job_success_threshold"]

    if success_rate >= (success_threshold * 100):
        expected_status = "complete"
    elif success_rate > 0:
        expected_status = "partial"
    else:
        expected_status = "failed"

    actual_status = job.status.value
    status_correct = actual_status == expected_status

    # Valid if all items accounted for AND success rate meets threshold
    all_accounted = unaccounted == 0
    meets_threshold = success_rate >= (success_threshold * 100)
    valid = all_accounted and meets_threshold

    return {
        "job_id": job_id,
        "valid": valid,
        "total_items": total,
        "completed_items": completed,
        "failed_items": failed,
        "unaccounted_items": unaccounted,
        "coverage_pct": round(coverage_pct, 2),
        "success_rate": round(success_rate, 2),
        "expected_status": expected_status,
        "actual_status": actual_status,
        "status_correct": status_correct,
    }


def correct_job_status(job_id: str) -> dict[str, Any]:
    """Correct job status if it doesn't match the expected status based on success rate.

    Implements VALID-07: Enforce 95% success threshold for 'complete' status.

    If a job processor set status to 'complete' but success rate is <95%, this
    corrects it to 'partial'. Similarly, if success rate is 0%, corrects to 'failed'.

    Args:
        job_id: UUID of the backfill job

    Returns:
        Dictionary with correction details:
        {
            "job_id": str,
            "corrected": bool,  # True if status was changed
            "old_status": str,
            "new_status": str,
        }

    Notes:
        - Calls update_job_status() if correction is needed
        - Logs warning when correction is applied
        - Returns corrected=False if status already matches expected
    """
    completeness = validate_job_completeness(job_id)

    if "error" in completeness:
        return {
            "job_id": job_id,
            "corrected": False,
            "error": completeness["error"],
        }

    if completeness["status_correct"]:
        return {
            "job_id": job_id,
            "corrected": False,
            "old_status": completeness["actual_status"],
            "new_status": completeness["actual_status"],
        }

    # Status correction needed
    old_status = completeness["actual_status"]
    new_status = completeness["expected_status"]
    success_rate = completeness["success_rate"]

    logger.warning(
        f"Job {job_id} status corrected: {old_status} -> {new_status} "
        f"(success_rate={success_rate}%)"
    )

    # Update the job status
    update_job_status(job_id, new_status)

    return {
        "job_id": job_id,
        "corrected": True,
        "old_status": old_status,
        "new_status": new_status,
    }


def get_freshness_report() -> dict[str, Any]:
    """Generate freshness report for all data types.

    Implements VALID-02: Monitor data staleness across baselines, search terms, keywords.

    Thresholds:
    - Baselines: 60 days (from VALIDATION_THRESHOLDS)
    - Search terms: 7 days
    - Keywords: 30 days

    Returns:
        Dictionary with freshness metrics:
        {
            "generated_at": str,  # ISO timestamp
            "total_skus": int,  # from variant_index
            "baselines": {
                "fresh_count": int,
                "stale_count": int,
                "missing_count": int,
                "threshold_days": 60,
            },
            "search_terms": {
                "fresh_count": int,
                "stale_count": int,
                "missing_count": int,
                "threshold_days": 7,
            },
            "keywords": {
                "fresh_count": int,
                "stale_count": int,
                "threshold_days": 30,
            },
        }

    Notes:
        - Queries variant_index for total SKU count (expected ~2,784)
        - Uses created_at for baselines, fetched_at for search terms, updated_at for keywords
        - Missing count = total_skus - (fresh + stale)
    """
    supabase = get_client()
    now = datetime.now(timezone.utc)

    # Get thresholds from config
    baseline_threshold_days = VALIDATION_THRESHOLDS["baseline_freshness_days"]
    search_threshold_days = VALIDATION_THRESHOLDS["search_terms_freshness_days"]
    keyword_threshold_days = VALIDATION_THRESHOLDS["keyword_cache_ttl_days"]

    # Calculate threshold dates
    baseline_threshold = now - timedelta(days=baseline_threshold_days)
    search_threshold = now - timedelta(days=search_threshold_days)
    keyword_threshold = now - timedelta(days=keyword_threshold_days)

    # Get total SKU count from variant_index
    total_skus_result = supabase.table("variant_index").select(
        "master_sku"
    ).execute()
    total_skus = len(set(row["master_sku"] for row in total_skus_result.data if row.get("master_sku")))

    # Baselines freshness (using created_at)
    # Count distinct master_skus with fresh/stale baseline data
    baseline_fresh_data = supabase.table("performance_baselines").select(
        "master_sku"
    ).gte("created_at", baseline_threshold.isoformat()).execute()

    baseline_stale_data = supabase.table("performance_baselines").select(
        "master_sku"
    ).lt("created_at", baseline_threshold.isoformat()).execute()

    baseline_fresh_skus = set(row["master_sku"] for row in baseline_fresh_data.data if row.get("master_sku"))
    baseline_stale_skus = set(row["master_sku"] for row in baseline_stale_data.data if row.get("master_sku"))

    baseline_fresh_count = len(baseline_fresh_skus)
    baseline_stale_count = len(baseline_stale_skus - baseline_fresh_skus)  # Exclude SKUs that have both fresh and stale
    baseline_missing_count = max(0, total_skus - baseline_fresh_count - baseline_stale_count)

    # Search terms freshness (using fetched_at)
    # Count distinct master_skus with fresh/stale data
    search_fresh_data = supabase.table("search_queries").select(
        "master_sku"
    ).gte("fetched_at", search_threshold.isoformat()).execute()

    search_stale_data = supabase.table("search_queries").select(
        "master_sku"
    ).lt("fetched_at", search_threshold.isoformat()).execute()

    search_fresh_skus = set(row["master_sku"] for row in search_fresh_data.data if row.get("master_sku"))
    search_stale_skus = set(row["master_sku"] for row in search_stale_data.data if row.get("master_sku"))

    search_fresh_count = len(search_fresh_skus)
    search_stale_count = len(search_stale_skus - search_fresh_skus)  # Exclude SKUs that have both
    search_missing_count = max(0, total_skus - search_fresh_count - search_stale_count)

    # Keywords freshness (using updated_at)
    keyword_fresh = supabase.table("keyword_metrics").select(
        "keyword", count="exact"
    ).gte("updated_at", keyword_threshold.isoformat()).execute()

    keyword_stale = supabase.table("keyword_metrics").select(
        "keyword", count="exact"
    ).lt("updated_at", keyword_threshold.isoformat()).execute()

    keyword_fresh_count = keyword_fresh.count or 0
    keyword_stale_count = keyword_stale.count or 0

    return {
        "generated_at": now.isoformat(),
        "total_skus": total_skus,
        "baselines": {
            "fresh_count": baseline_fresh_count,
            "stale_count": baseline_stale_count,
            "missing_count": baseline_missing_count,
            "threshold_days": baseline_threshold_days,
        },
        "search_terms": {
            "fresh_count": search_fresh_count,
            "stale_count": search_stale_count,
            "missing_count": search_missing_count,
            "threshold_days": search_threshold_days,
        },
        "keywords": {
            "fresh_count": keyword_fresh_count,
            "stale_count": keyword_stale_count,
            "threshold_days": keyword_threshold_days,
        },
    }


def detect_metric_outliers(
    metric_name: str = "avg_ctr",
    z_threshold: float = 3.0
) -> dict[str, Any]:
    """Detect statistical outliers in performance metrics using Z-scores.

    Implements VALID-10: Flag anomalous metric values for manual review.

    Args:
        metric_name: Column name in performance_baselines (e.g., "avg_ctr", "avg_cvr")
        z_threshold: Z-score threshold for outlier detection (default 3.0)

    Returns:
        Dictionary with outlier analysis:
        {
            "metric": str,
            "z_threshold": float,
            "total_records": int,
            "outlier_count": int,
            "outliers": [
                {
                    "master_sku": str,
                    "platform": str,
                    "value": float,
                    "z_score": float,
                }
            ],
            "distribution": {
                "mean": float,
                "std": float,
                "min": float,
                "max": float,
            }
        }

    Notes:
        - Requires scipy for Z-score calculation
        - Returns error dict if scipy not installed
        - Returns empty outliers list if fewer than 3 records
        - Uses np.abs(stats.zscore(values)) for calculation
    """
    if not HAS_SCIPY:
        return {
            "error": "scipy not installed",
            "metric": metric_name,
            "outliers": [],
        }

    supabase = get_client()

    # Query all records with the specified metric
    result = supabase.table("performance_baselines").select(
        f"master_sku, platform, {metric_name}"
    ).not_.is_(metric_name, "null").execute()

    if not result.data or len(result.data) < 3:
        return {
            "metric": metric_name,
            "z_threshold": z_threshold,
            "total_records": len(result.data) if result.data else 0,
            "outlier_count": 0,
            "outliers": [],
            "distribution": {},
        }

    # Extract values and calculate Z-scores
    values = np.array([float(row[metric_name]) for row in result.data])
    z_scores = np.abs(stats.zscore(values))

    # Calculate distribution stats
    distribution = {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }

    # Find outliers
    outliers = []
    for i, (row, z_score) in enumerate(zip(result.data, z_scores)):
        if z_score > z_threshold:
            outliers.append({
                "master_sku": row["master_sku"],
                "platform": row["platform"],
                "value": float(row[metric_name]),
                "z_score": float(z_score),
            })

    logger.info(
        f"Outlier detection for {metric_name}: {len(outliers)} outliers found "
        f"(threshold: {z_threshold}, total: {len(result.data)})"
    )

    return {
        "metric": metric_name,
        "z_threshold": z_threshold,
        "total_records": len(result.data),
        "outlier_count": len(outliers),
        "outliers": sorted(outliers, key=lambda x: x["z_score"], reverse=True),
        "distribution": distribution,
    }


def generate_full_quality_report(job_id: str | None = None) -> dict[str, Any]:
    """Generate comprehensive quality report combining all validation checks.

    Args:
        job_id: Optional UUID of a specific job to validate

    Returns:
        Dictionary with all quality metrics:
        {
            "generated_at": str,
            "completeness": dict | None,  # Only if job_id provided
            "freshness": dict,
            "outliers": dict,
        }

    Notes:
        - Completeness check only runs if job_id is provided
        - Freshness report always runs
        - Outlier detection runs for avg_ctr metric
        - Each section can be accessed independently
    """
    now = datetime.now(timezone.utc)

    report: dict[str, Any] = {
        "generated_at": now.isoformat(),
    }

    # Completeness check (if job_id provided)
    if job_id:
        report["completeness"] = validate_job_completeness(job_id)

    # Freshness report
    report["freshness"] = get_freshness_report()

    # Outlier detection
    report["outliers"] = detect_metric_outliers(metric_name="avg_ctr")

    return report
