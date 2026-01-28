"""Data-driven batch selection for publishing optimized content.

This module implements SKU selection logic for batch publishing based on
performance data from Google Ads and GA4 analytics. It follows the pilot
selection methodology:

1. Fetch performance data (impressions, clicks, CVR, ROAS, revenue)
2. Exclude top N revenue SKUs (risk management)
3. Tier SKUs by efficiency metrics
4. Select proportionally from each tier
5. Ensure category diversity
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from feedops.db import get_approved_for_batch, get_performance_baseline

logger = logging.getLogger(__name__)


@dataclass
class SKUPerformance:
    """Performance data for a SKU."""

    master_sku: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0
    cost: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    roas: float = 0.0
    category: str | None = None
    collection: str | None = None

    @property
    def efficiency_score(self) -> float:
        """Calculate efficiency score for tiering.

        Higher is better. Combines CVR and ROAS with traffic weighting.
        """
        if self.impressions == 0:
            return 0.0

        # Normalize metrics to 0-1 scale for combination
        # CVR typically 0-5%, normalize to 0-1 by dividing by 0.05
        normalized_cvr = min(self.cvr / 0.05, 1.0)

        # ROAS typically 0-10, normalize to 0-1 by dividing by 10
        normalized_roas = min(self.roas / 10.0, 1.0)

        # Weight: 60% CVR, 40% ROAS
        return (normalized_cvr * 0.6) + (normalized_roas * 0.4)

    @property
    def traffic_tier(self) -> str:
        """Classify SKU by traffic volume.

        Returns:
            'high', 'medium', or 'low'
        """
        if self.impressions >= 1000:
            return "high"
        elif self.impressions >= 100:
            return "medium"
        return "low"


@dataclass
class BatchSelectionCriteria:
    """Configuration for batch selection."""

    # Exclusion rules
    exclude_top_revenue_count: int = 5
    min_impressions: int = 10  # Minimum traffic for inclusion

    # Tier distribution (must sum to 1.0)
    tier_distribution: dict[str, float] = field(
        default_factory=lambda: {
            "tier1_efficiency": 0.20,  # High efficiency SKUs
            "tier2_moderate": 0.50,  # Moderate efficiency SKUs
            "tier3_high_traffic": 0.20,  # High traffic, testing opportunity
            "fill": 0.10,  # Remaining slots
        }
    )

    # Category diversity (max SKUs from single category)
    max_per_category: int | None = None  # None = no limit

    # Selection lookback for performance data
    lookback_days: int = 30


def select_batch_by_performance(
    approved_skus: list[dict],
    batch_size: int,
    *,
    db_path: Path,
    ads_data: dict[str, dict] | None = None,
    ga4_data: dict[str, dict] | None = None,
    criteria: BatchSelectionCriteria | None = None,
) -> list[str]:
    """Select SKUs for a batch using performance data.

    Follows the pilot selection methodology:
    1. Fetch Google Ads performance (impressions, clicks, CVR, ROAS)
    2. Fetch GA4 analytics (revenue, purchases) if available
    3. Exclude top N revenue SKUs (risk management)
    4. Tier SKUs by efficiency (Tier1=high efficiency, Tier2=mid, Tier3=high traffic)
    5. Select proportionally from each tier
    6. Ensure category diversity

    Args:
        approved_skus: List of approved SKU dicts from get_approved_for_batch().
        batch_size: Target number of SKUs to select.
        db_path: Path to the database.
        ads_data: Optional pre-fetched Google Ads data keyed by SKU.
        ga4_data: Optional pre-fetched GA4 data keyed by SKU.
        criteria: Selection criteria configuration.

    Returns:
        List of selected master_skus.
    """
    if criteria is None:
        criteria = BatchSelectionCriteria()

    if not approved_skus:
        logger.warning("No approved SKUs provided for batch selection")
        return []

    # Build performance data for each approved SKU
    sku_performance: list[SKUPerformance] = []

    for approval in approved_skus:
        master_sku = approval["master_sku"]

        # Start with baseline data from database
        perf = SKUPerformance(master_sku=master_sku)

        # Try to get baseline performance from database
        baseline = get_performance_baseline(
            db_path, master_sku=master_sku, platform="google"
        )
        if baseline:
            perf.impressions = int(baseline.get("avg_impressions", 0) or 0)
            perf.clicks = int(baseline.get("avg_clicks", 0) or 0)
            perf.ctr = float(baseline.get("avg_ctr", 0) or 0)
            perf.conversions = int(baseline.get("avg_conversions", 0) or 0)
            perf.revenue = float(baseline.get("avg_conversion_value", 0) or 0)
            perf.cvr = float(baseline.get("avg_cvr", 0) or 0)
            perf.roas = float(baseline.get("avg_roas", 0) or 0)
            perf.cost = float(baseline.get("avg_cost", 0) or 0)

        # Override with provided ads_data if available
        if ads_data and master_sku in ads_data:
            ad = ads_data[master_sku]
            perf.impressions = int(ad.get("impressions", perf.impressions))
            perf.clicks = int(ad.get("clicks", perf.clicks))
            perf.ctr = float(ad.get("ctr", perf.ctr))
            perf.conversions = int(ad.get("conversions", perf.conversions))
            perf.cost = float(ad.get("cost", perf.cost))
            if perf.impressions > 0 and perf.clicks > 0:
                perf.ctr = perf.clicks / perf.impressions
            if perf.impressions > 0 and perf.conversions > 0:
                perf.cvr = perf.conversions / perf.impressions
            if perf.cost > 0:
                perf.roas = perf.revenue / perf.cost if perf.revenue > 0 else 0

        # Override with GA4 data if available (mainly for revenue)
        if ga4_data and master_sku in ga4_data:
            ga = ga4_data[master_sku]
            perf.revenue = float(ga.get("revenue", perf.revenue))
            perf.conversions = int(ga.get("purchases", perf.conversions))

        sku_performance.append(perf)

    # Step 1: Exclude top revenue SKUs (risk management)
    sorted_by_revenue = sorted(sku_performance, key=lambda x: x.revenue, reverse=True)
    excluded_skus = {
        p.master_sku for p in sorted_by_revenue[: criteria.exclude_top_revenue_count]
    }
    logger.info(f"Excluding {len(excluded_skus)} top revenue SKUs: {excluded_skus}")

    # Filter out excluded and low-traffic SKUs
    candidates = [
        p
        for p in sku_performance
        if p.master_sku not in excluded_skus
        and p.impressions >= criteria.min_impressions
    ]

    # If we don't have enough candidates with traffic, include low-traffic ones
    if len(candidates) < batch_size:
        low_traffic = [
            p
            for p in sku_performance
            if p.master_sku not in excluded_skus
            and p.impressions < criteria.min_impressions
        ]
        candidates.extend(low_traffic)

    logger.info(f"Total candidates after exclusions: {len(candidates)}")

    # Step 2: Tier SKUs by efficiency
    tier1_efficiency: list[SKUPerformance] = []
    tier2_moderate: list[SKUPerformance] = []
    tier3_high_traffic: list[SKUPerformance] = []
    fill_tier: list[SKUPerformance] = []

    # Sort by efficiency for tiering
    sorted_by_efficiency = sorted(
        candidates, key=lambda x: x.efficiency_score, reverse=True
    )

    for i, perf in enumerate(sorted_by_efficiency):
        # Top 20% by efficiency -> Tier 1
        if i < len(sorted_by_efficiency) * 0.2:
            tier1_efficiency.append(perf)
        # Next 50% -> Tier 2
        elif i < len(sorted_by_efficiency) * 0.7:
            tier2_moderate.append(perf)
        # High traffic SKUs -> Tier 3
        elif perf.traffic_tier == "high":
            tier3_high_traffic.append(perf)
        # Rest -> Fill tier
        else:
            fill_tier.append(perf)

    tiers = {
        "tier1_efficiency": tier1_efficiency,
        "tier2_moderate": tier2_moderate,
        "tier3_high_traffic": tier3_high_traffic,
        "fill": fill_tier,
    }

    logger.info(
        f"Tier distribution: {', '.join(f'{k}={len(v)}' for k, v in tiers.items())}"
    )

    # Step 3: Select proportionally from each tier
    selected: list[str] = []
    category_counts: dict[str, int] = defaultdict(int)

    for tier_name, tier_fraction in criteria.tier_distribution.items():
        tier_skus = tiers.get(tier_name, [])
        tier_target = int(batch_size * tier_fraction)

        # Skip tier if target is 0 (would cause division by zero)
        if tier_target <= 0:
            continue

        # Sort tier by efficiency for selection
        tier_sorted = sorted(tier_skus, key=lambda x: x.efficiency_score, reverse=True)

        for perf in tier_sorted:
            if len(selected) >= batch_size:
                break

            # Check category diversity limit
            if (
                criteria.max_per_category is not None
                and perf.category
                and category_counts[perf.category] >= criteria.max_per_category
            ):
                continue

            if perf.master_sku not in selected:
                selected.append(perf.master_sku)
                if perf.category:
                    category_counts[perf.category] += 1

            # Check if we've filled this tier's allocation
            if len(selected) >= (len(selected) // tier_target + 1) * tier_target:
                break

    # Fill remaining slots if needed
    if len(selected) < batch_size:
        remaining = batch_size - len(selected)
        all_remaining = [p for p in candidates if p.master_sku not in selected]
        all_remaining_sorted = sorted(
            all_remaining, key=lambda x: x.efficiency_score, reverse=True
        )

        for perf in all_remaining_sorted[:remaining]:
            if perf.master_sku not in selected:
                selected.append(perf.master_sku)

    logger.info(f"Selected {len(selected)} SKUs for batch")
    return selected


def get_batch_selection_summary(
    selected_skus: list[str],
    all_performance: dict[str, SKUPerformance],
) -> dict[str, Any]:
    """Generate a summary of the batch selection.

    Args:
        selected_skus: List of selected master_skus.
        all_performance: Dict mapping SKU to performance data.

    Returns:
        Summary dict with statistics about the selection.
    """
    if not selected_skus:
        return {"total": 0, "error": "No SKUs selected"}

    selected_perf = [
        all_performance.get(sku) for sku in selected_skus if sku in all_performance
    ]

    if not selected_perf:
        return {"total": len(selected_skus), "performance_data_available": False}

    total_impressions = sum(p.impressions for p in selected_perf if p)
    total_revenue = sum(p.revenue for p in selected_perf if p)
    avg_efficiency = sum(p.efficiency_score for p in selected_perf if p) / len(
        selected_perf
    )

    # Category distribution
    category_dist: dict[str, int] = defaultdict(int)
    for p in selected_perf:
        if p and p.category:
            category_dist[p.category] += 1

    # Traffic tier distribution
    traffic_dist: dict[str, int] = defaultdict(int)
    for p in selected_perf:
        if p:
            traffic_dist[p.traffic_tier] += 1

    return {
        "total": len(selected_skus),
        "total_impressions": total_impressions,
        "total_revenue": total_revenue,
        "avg_efficiency_score": round(avg_efficiency, 3),
        "category_distribution": dict(category_dist),
        "traffic_distribution": dict(traffic_dist),
    }
