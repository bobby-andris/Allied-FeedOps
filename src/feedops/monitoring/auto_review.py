"""Automated performance review for FeedOps content.

Automatically reviews published SKUs and generates recommendations
for keeping, monitoring, or rolling back FeedOps-optimized content.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from feedops.db.schema import (
    get_performance_baseline,
    get_performance_snapshots,
    get_published_skus_for_review,
)
from feedops.monitoring.significance import test_significance

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_ROLLBACK_THRESHOLD = -0.15  # -15% ROAS decline triggers rollback
DEFAULT_MONITOR_THRESHOLD = -0.05  # -5% to -15% = monitor
DEFAULT_MIN_DAYS = 14  # Minimum days for statistical significance


def auto_review_performance(
    *,
    platform: str,
    min_days_since_publish: int = DEFAULT_MIN_DAYS,
    rollback_threshold: float = DEFAULT_ROLLBACK_THRESHOLD,
    monitor_threshold: float = DEFAULT_MONITOR_THRESHOLD,
    db_path: Path | str,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """Automatically review all published SKUs and flag underperformers.

    Process:
    1. Query publish_events for SKUs published >= min_days ago
    2. Fetch current performance from platform APIs
    3. Compare to baseline (from performance_baselines table)
    4. Flag SKUs with ROAS decline > rollback_threshold
    5. Generate recommendations: 'keep', 'monitor', 'rollback'

    Args:
        platform: Platform to review ('google', 'bing', 'shopify').
        min_days_since_publish: Minimum days for statistical significance.
        rollback_threshold: ROAS decline threshold for auto-rollback (e.g., -0.15 for -15%).
        monitor_threshold: ROAS decline threshold for monitoring (e.g., -0.05 for -5%).
        db_path: Path to SQLite database.
        environment: Optional environment filter ('staging', 'production').

    Returns:
        List of review results:
        [
            {
                'sku': str,
                'platform': str,
                'environment': str,
                'published_at': str,
                'days_since_publish': int,
                'baseline_roas': float,
                'current_roas': float,
                'delta_roas': float,
                'delta_roas_pct': float,
                'baseline_ctr': float,
                'current_ctr': float,
                'delta_ctr': float,
                'delta_ctr_pct': float,
                'is_significant': bool,
                'p_value': float or None,
                'sample_size_adequate': bool,
                'recommendation': str ('keep', 'monitor', 'rollback'),
                'reason': str
            }
        ]
    """
    db_path = Path(db_path)

    # Get published SKUs ready for review
    published_skus = get_published_skus_for_review(
        db_path,
        platform=platform,
        min_days_since_publish=min_days_since_publish,
        environment=environment,
    )

    if not published_skus:
        logger.info(
            "No SKUs found for review (platform=%s, min_days=%d)",
            platform,
            min_days_since_publish,
        )
        return []

    results: list[dict[str, Any]] = []

    for publish_event in published_skus:
        sku = publish_event["master_sku"]
        env = publish_event["environment"]
        published_at = publish_event["published_at"]

        # Calculate days since publish
        try:
            pub_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            days_since = (datetime.now(pub_date.tzinfo) - pub_date).days
        except (ValueError, TypeError):
            days_since = min_days_since_publish

        # Get baseline metrics
        baseline = get_performance_baseline(db_path, master_sku=sku, platform=platform)

        if not baseline:
            logger.debug("No baseline found for %s on %s", sku, platform)
            results.append(
                _create_review_result(
                    sku=sku,
                    platform=platform,
                    environment=env,
                    published_at=published_at,
                    days_since_publish=days_since,
                    recommendation="monitor",
                    reason="No baseline data available for comparison",
                )
            )
            continue

        # Get current performance snapshots
        # Look at the most recent snapshot date range
        snapshots = get_performance_snapshots(
            db_path,
            master_sku=sku,
            platform=platform,
            limit=30,  # Last 30 days of snapshots
        )

        if not snapshots:
            logger.debug("No performance snapshots found for %s on %s", sku, platform)
            results.append(
                _create_review_result(
                    sku=sku,
                    platform=platform,
                    environment=env,
                    published_at=published_at,
                    days_since_publish=days_since,
                    recommendation="monitor",
                    reason="No current performance data available",
                )
            )
            continue

        # Aggregate current metrics from snapshots
        current_metrics = _aggregate_snapshots(snapshots)

        # Compare to baseline
        review_result = _compare_performance(
            sku=sku,
            platform=platform,
            environment=env,
            published_at=published_at,
            days_since_publish=days_since,
            baseline=baseline,
            current=current_metrics,
            rollback_threshold=rollback_threshold,
            monitor_threshold=monitor_threshold,
        )

        results.append(review_result)

    # Sort by delta_roas ascending (worst performers first)
    results.sort(key=lambda x: x.get("delta_roas", 0) or 0)

    return results


def _aggregate_snapshots(snapshots: list[dict]) -> dict[str, Any]:
    """Aggregate multiple snapshots into summary metrics."""
    if not snapshots:
        return {
            "impressions": 0,
            "clicks": 0,
            "ctr": 0.0,
            "conversions": 0,
            "conversion_value": 0.0,
            "cost": 0.0,
            "roas": 0.0,
        }

    total_impressions = sum(s.get("impressions", 0) or 0 for s in snapshots)
    total_clicks = sum(s.get("clicks", 0) or 0 for s in snapshots)
    total_conversions = sum(s.get("conversions", 0) or 0 for s in snapshots)
    total_conversion_value = sum(
        s.get("conversion_value", 0.0) or 0.0 for s in snapshots
    )
    total_cost = sum(s.get("cost", 0.0) or 0.0 for s in snapshots)

    ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0
    roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

    return {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "ctr": ctr,
        "conversions": total_conversions,
        "conversion_value": total_conversion_value,
        "cvr": cvr,
        "cost": total_cost,
        "roas": roas,
    }


def _compare_performance(
    *,
    sku: str,
    platform: str,
    environment: str,
    published_at: str,
    days_since_publish: int,
    baseline: dict,
    current: dict,
    rollback_threshold: float,
    monitor_threshold: float,
) -> dict[str, Any]:
    """Compare baseline vs current performance and generate recommendation."""
    baseline_roas = baseline.get("avg_roas", 0.0) or 0.0
    baseline_ctr = baseline.get("avg_ctr", 0.0) or 0.0
    baseline_conversions = int(baseline.get("avg_conversions", 0) or 0)
    baseline_impressions = int(baseline.get("avg_impressions", 0) or 0)

    current_roas = current.get("roas", 0.0) or 0.0
    current_ctr = current.get("ctr", 0.0) or 0.0
    current_conversions = current.get("conversions", 0) or 0
    current_impressions = current.get("impressions", 0) or 0

    # Calculate deltas
    delta_roas = current_roas - baseline_roas
    delta_roas_pct = delta_roas / baseline_roas if baseline_roas > 0 else 0.0

    delta_ctr = current_ctr - baseline_ctr
    delta_ctr_pct = delta_ctr / baseline_ctr if baseline_ctr > 0 else 0.0

    # Test statistical significance for conversions
    # Scale baseline to match test period duration if needed
    # For simplicity, we assume same time period or use averages
    sig_result = test_significance(
        baseline_conversions=max(baseline_conversions, 1),
        baseline_impressions=max(baseline_impressions, 1),
        test_conversions=current_conversions,
        test_impressions=current_impressions,
        confidence_level=0.95,
    )

    is_significant = sig_result.get("is_significant", False)
    p_value = sig_result.get("p_value")
    sample_size_adequate = sig_result.get("sample_size_adequate", False)

    # Determine recommendation
    recommendation, reason = _determine_recommendation(
        delta_roas_pct=delta_roas_pct,
        delta_ctr_pct=delta_ctr_pct,
        is_significant=is_significant,
        sample_size_adequate=sample_size_adequate,
        rollback_threshold=rollback_threshold,
        monitor_threshold=monitor_threshold,
    )

    return {
        "sku": sku,
        "platform": platform,
        "environment": environment,
        "published_at": published_at,
        "days_since_publish": days_since_publish,
        "baseline_roas": round(baseline_roas, 4),
        "current_roas": round(current_roas, 4),
        "delta_roas": round(delta_roas, 4),
        "delta_roas_pct": round(delta_roas_pct, 4),
        "baseline_ctr": round(baseline_ctr, 6),
        "current_ctr": round(current_ctr, 6),
        "delta_ctr": round(delta_ctr, 6),
        "delta_ctr_pct": round(delta_ctr_pct, 4),
        "baseline_impressions": baseline_impressions,
        "current_impressions": current_impressions,
        "baseline_conversions": baseline_conversions,
        "current_conversions": current_conversions,
        "is_significant": is_significant,
        "p_value": p_value,
        "sample_size_adequate": sample_size_adequate,
        "recommendation": recommendation,
        "reason": reason,
    }


def _determine_recommendation(
    *,
    delta_roas_pct: float,
    delta_ctr_pct: float,
    is_significant: bool,
    sample_size_adequate: bool,
    rollback_threshold: float,
    monitor_threshold: float,
) -> tuple[str, str]:
    """Determine recommendation based on performance metrics.

    Decision logic:
    - rollback: ROAS decline > rollback_threshold AND statistically significant
    - monitor: ROAS decline between monitor_threshold and rollback_threshold
               OR insufficient data for significance
    - keep: ROAS stable/improved OR decline not significant
    """
    # Format percentages for display
    roas_pct_str = f"{delta_roas_pct * 100:+.1f}%"
    ctr_pct_str = f"{delta_ctr_pct * 100:+.1f}%"

    if not sample_size_adequate:
        return (
            "monitor",
            f"Insufficient sample size for reliable testing. "
            f"ROAS: {roas_pct_str}, CTR: {ctr_pct_str}. Continue monitoring.",
        )

    # Significant decline exceeds rollback threshold
    if delta_roas_pct <= rollback_threshold and is_significant:
        return (
            "rollback",
            f"ROAS declined {roas_pct_str} (exceeds {rollback_threshold * 100:.0f}% threshold). "
            f"Statistically significant - recommend rollback.",
        )

    # Decline in monitor zone (between thresholds)
    if monitor_threshold >= delta_roas_pct > rollback_threshold:
        if is_significant:
            return (
                "monitor",
                f"ROAS declined {roas_pct_str} (within monitoring range). "
                f"Statistically significant - continue monitoring closely.",
            )
        else:
            return (
                "monitor",
                f"ROAS declined {roas_pct_str} but not statistically significant. "
                f"Continue monitoring for more data.",
            )

    # Decline but not significant
    if delta_roas_pct < 0 and not is_significant:
        return (
            "monitor",
            f"ROAS declined {roas_pct_str} but change is not statistically significant. "
            f"Likely random variance - continue monitoring.",
        )

    # Performance improved or stable
    if delta_roas_pct >= 0:
        if is_significant:
            return (
                "keep",
                f"ROAS improved {roas_pct_str} (statistically significant). "
                f"CTR: {ctr_pct_str}. FeedOps content is performing well.",
            )
        else:
            return (
                "keep",
                f"ROAS: {roas_pct_str}, CTR: {ctr_pct_str}. "
                f"Performance stable - keep FeedOps content.",
            )

    # Default fallback
    return (
        "monitor",
        f"ROAS: {roas_pct_str}, CTR: {ctr_pct_str}. Continue monitoring.",
    )


def _create_review_result(
    *,
    sku: str,
    platform: str,
    environment: str,
    published_at: str,
    days_since_publish: int,
    recommendation: str,
    reason: str,
) -> dict[str, Any]:
    """Create a review result with missing data."""
    return {
        "sku": sku,
        "platform": platform,
        "environment": environment,
        "published_at": published_at,
        "days_since_publish": days_since_publish,
        "baseline_roas": None,
        "current_roas": None,
        "delta_roas": None,
        "delta_roas_pct": None,
        "baseline_ctr": None,
        "current_ctr": None,
        "delta_ctr": None,
        "delta_ctr_pct": None,
        "baseline_impressions": None,
        "current_impressions": None,
        "baseline_conversions": None,
        "current_conversions": None,
        "is_significant": False,
        "p_value": None,
        "sample_size_adequate": False,
        "recommendation": recommendation,
        "reason": reason,
    }


def generate_review_summary(
    reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate a summary of auto-review results.

    Args:
        reviews: List of review results from auto_review_performance.

    Returns:
        Summary dictionary with counts and averages.
    """
    if not reviews:
        return {
            "total_reviewed": 0,
            "keep_count": 0,
            "monitor_count": 0,
            "rollback_count": 0,
            "avg_roas_lift": None,
            "avg_ctr_lift": None,
            "significant_improvements": 0,
            "significant_declines": 0,
        }

    keep_count = sum(1 for r in reviews if r["recommendation"] == "keep")
    monitor_count = sum(1 for r in reviews if r["recommendation"] == "monitor")
    rollback_count = sum(1 for r in reviews if r["recommendation"] == "rollback")

    # Calculate average lifts (only for reviews with data)
    roas_lifts = [
        r["delta_roas_pct"] for r in reviews if r["delta_roas_pct"] is not None
    ]
    ctr_lifts = [r["delta_ctr_pct"] for r in reviews if r["delta_ctr_pct"] is not None]

    avg_roas_lift = sum(roas_lifts) / len(roas_lifts) if roas_lifts else None
    avg_ctr_lift = sum(ctr_lifts) / len(ctr_lifts) if ctr_lifts else None

    significant_improvements = sum(
        1
        for r in reviews
        if r.get("is_significant") and (r.get("delta_roas_pct") or 0) > 0
    )
    significant_declines = sum(
        1
        for r in reviews
        if r.get("is_significant") and (r.get("delta_roas_pct") or 0) < 0
    )

    return {
        "total_reviewed": len(reviews),
        "keep_count": keep_count,
        "monitor_count": monitor_count,
        "rollback_count": rollback_count,
        "avg_roas_lift": round(avg_roas_lift, 4) if avg_roas_lift is not None else None,
        "avg_ctr_lift": round(avg_ctr_lift, 4) if avg_ctr_lift is not None else None,
        "significant_improvements": significant_improvements,
        "significant_declines": significant_declines,
    }


def format_review_report(
    reviews: list[dict[str, Any]],
    summary: dict[str, Any] | None = None,
) -> str:
    """Format review results as a text report.

    Args:
        reviews: List of review results.
        summary: Optional pre-computed summary.

    Returns:
        Formatted text report.
    """
    if summary is None:
        summary = generate_review_summary(reviews)

    lines = [
        "=" * 60,
        "FeedOps Performance Auto-Review Report",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 40,
        f"Total SKUs Reviewed: {summary['total_reviewed']}",
        f"  Keep:     {summary['keep_count']}",
        f"  Monitor:  {summary['monitor_count']}",
        f"  Rollback: {summary['rollback_count']}",
        "",
    ]

    if summary["avg_roas_lift"] is not None:
        lines.append(f"Average ROAS Lift: {summary['avg_roas_lift'] * 100:+.1f}%")
    if summary["avg_ctr_lift"] is not None:
        lines.append(f"Average CTR Lift:  {summary['avg_ctr_lift'] * 100:+.1f}%")

    lines.extend(
        [
            f"Significant Improvements: {summary['significant_improvements']}",
            f"Significant Declines:     {summary['significant_declines']}",
            "",
        ]
    )

    # Group by recommendation
    for rec_type in ["rollback", "monitor", "keep"]:
        rec_reviews = [r for r in reviews if r["recommendation"] == rec_type]
        if not rec_reviews:
            continue

        emoji = {"rollback": "X", "monitor": "?", "keep": "OK"}[rec_type]
        lines.extend(
            [
                "",
                f"{emoji} {rec_type.upper()} ({len(rec_reviews)} SKUs)",
                "-" * 40,
            ]
        )

        for r in rec_reviews:
            roas_str = (
                f"{r['delta_roas_pct'] * 100:+.1f}%"
                if r["delta_roas_pct"] is not None
                else "N/A"
            )
            ctr_str = (
                f"{r['delta_ctr_pct'] * 100:+.1f}%"
                if r["delta_ctr_pct"] is not None
                else "N/A"
            )
            sig_str = "Yes" if r["is_significant"] else "No"

            lines.extend(
                [
                    f"  {r['sku']} ({r['platform']}, {r['environment']})",
                    f"    ROAS: {roas_str}  |  CTR: {ctr_str}  |  Significant: {sig_str}",
                    f"    {r['reason']}",
                    "",
                ]
            )

    lines.append("=" * 60)

    return "\n".join(lines)
