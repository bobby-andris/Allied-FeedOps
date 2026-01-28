"""Statistical significance testing for performance comparisons.

Provides chi-square tests for comparing conversion rates between
baseline and test periods, with minimum sample size requirements.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# Minimum thresholds for reliable statistical tests
MIN_IMPRESSIONS = 100
MIN_CONVERSIONS = 5


def test_significance(
    baseline_conversions: int,
    baseline_impressions: int,
    test_conversions: int,
    test_impressions: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Run chi-square test to determine if performance change is significant.

    Uses chi-square test of independence to compare conversion rates between
    baseline and test periods.

    Args:
        baseline_conversions: Number of conversions in baseline period.
        baseline_impressions: Number of impressions in baseline period.
        test_conversions: Number of conversions in test period.
        test_impressions: Number of impressions in test period.
        confidence_level: Desired confidence level (default 0.95 for 95%).

    Returns:
        Dictionary with test results:
        {
            'p_value': float or None,
            'is_significant': bool,
            'confidence': float,
            'test_type': str,
            'effect_size': float or None,
            'sample_size_adequate': bool,
            'baseline_rate': float or None,
            'test_rate': float or None,
            'lift': float or None (percentage change),
            'warning': str or None
        }

    Notes:
        - Minimum sample size: 100 impressions, 5 conversions per variant
        - Uses scipy.stats.chi2_contingency for the test
        - Effect size is calculated as relative improvement
    """
    # Check minimum sample sizes
    sample_size_adequate = (
        baseline_impressions >= MIN_IMPRESSIONS
        and test_impressions >= MIN_IMPRESSIONS
        and baseline_conversions >= MIN_CONVERSIONS
        and test_conversions >= MIN_CONVERSIONS
    )

    if not sample_size_adequate:
        warning_parts = []
        if baseline_impressions < MIN_IMPRESSIONS:
            warning_parts.append(
                f"baseline impressions ({baseline_impressions}) < {MIN_IMPRESSIONS}"
            )
        if test_impressions < MIN_IMPRESSIONS:
            warning_parts.append(
                f"test impressions ({test_impressions}) < {MIN_IMPRESSIONS}"
            )
        if baseline_conversions < MIN_CONVERSIONS:
            warning_parts.append(
                f"baseline conversions ({baseline_conversions}) < {MIN_CONVERSIONS}"
            )
        if test_conversions < MIN_CONVERSIONS:
            warning_parts.append(
                f"test conversions ({test_conversions}) < {MIN_CONVERSIONS}"
            )

        warning = f"Insufficient sample size: {'; '.join(warning_parts)}"

        # Calculate rates anyway for reference
        baseline_rate = (
            baseline_conversions / baseline_impressions
            if baseline_impressions > 0
            else None
        )
        test_rate = (
            test_conversions / test_impressions if test_impressions > 0 else None
        )

        lift = None
        if baseline_rate and test_rate and baseline_rate > 0:
            lift = (test_rate - baseline_rate) / baseline_rate

        return {
            "p_value": None,
            "is_significant": False,
            "confidence": confidence_level,
            "test_type": "chi_square",
            "effect_size": lift,
            "sample_size_adequate": False,
            "baseline_rate": baseline_rate,
            "test_rate": test_rate,
            "lift": lift,
            "warning": warning,
        }

    # Import scipy only when needed (keeps it optional for basic usage)
    try:
        from scipy import stats  # type: ignore[import-not-found]
    except ImportError:
        logger.error(
            "scipy is required for significance testing. "
            "Install with: pip install scipy>=1.10"
        )
        return {
            "p_value": None,
            "is_significant": False,
            "confidence": confidence_level,
            "test_type": "chi_square",
            "effect_size": None,
            "sample_size_adequate": True,
            "baseline_rate": None,
            "test_rate": None,
            "lift": None,
            "warning": "scipy not installed - cannot perform statistical test",
        }

    # Build contingency table
    # Rows: [baseline, test]
    # Cols: [conversions, non-conversions]
    baseline_non_conversions = baseline_impressions - baseline_conversions
    test_non_conversions = test_impressions - test_conversions

    # Ensure non-negative values
    if baseline_non_conversions < 0 or test_non_conversions < 0:
        return {
            "p_value": None,
            "is_significant": False,
            "confidence": confidence_level,
            "test_type": "chi_square",
            "effect_size": None,
            "sample_size_adequate": False,
            "baseline_rate": None,
            "test_rate": None,
            "lift": None,
            "warning": "Invalid data: conversions exceed impressions",
        }

    observed = [
        [baseline_conversions, baseline_non_conversions],
        [test_conversions, test_non_conversions],
    ]

    # Run chi-square test
    try:
        chi2, p_value, dof, expected = stats.chi2_contingency(observed)
    except Exception as e:
        logger.error("Chi-square test failed: %s", e)
        return {
            "p_value": None,
            "is_significant": False,
            "confidence": confidence_level,
            "test_type": "chi_square",
            "effect_size": None,
            "sample_size_adequate": True,
            "baseline_rate": None,
            "test_rate": None,
            "lift": None,
            "warning": f"Chi-square test failed: {e}",
        }

    # Calculate rates and effect size
    baseline_rate = baseline_conversions / baseline_impressions
    test_rate = test_conversions / test_impressions
    effect_size = (
        (test_rate - baseline_rate) / baseline_rate if baseline_rate > 0 else 0.0
    )
    lift = effect_size  # Same as effect_size, expressed as relative change

    # Determine significance
    alpha = 1 - confidence_level
    is_significant = p_value < alpha

    return {
        "p_value": round(p_value, 6),
        "is_significant": is_significant,
        "confidence": confidence_level,
        "test_type": "chi_square",
        "effect_size": round(effect_size, 4),
        "sample_size_adequate": True,
        "baseline_rate": round(baseline_rate, 6),
        "test_rate": round(test_rate, 6),
        "lift": round(lift, 4),
        "warning": None,
    }


def test_ctr_significance(
    baseline_clicks: int,
    baseline_impressions: int,
    test_clicks: int,
    test_impressions: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Test if CTR change is statistically significant.

    Convenience wrapper for test_significance that uses clicks as conversions.

    Args:
        baseline_clicks: Number of clicks in baseline period.
        baseline_impressions: Number of impressions in baseline period.
        test_clicks: Number of clicks in test period.
        test_impressions: Number of impressions in test period.
        confidence_level: Desired confidence level.

    Returns:
        Same format as test_significance, with rates renamed to ctr.
    """
    result = test_significance(
        baseline_conversions=baseline_clicks,
        baseline_impressions=baseline_impressions,
        test_conversions=test_clicks,
        test_impressions=test_impressions,
        confidence_level=confidence_level,
    )

    # Rename rate fields for clarity
    result["baseline_ctr"] = result.pop("baseline_rate")
    result["test_ctr"] = result.pop("test_rate")

    return result


def calculate_required_sample_size(
    baseline_rate: float,
    minimum_detectable_effect: float,
    confidence_level: float = 0.95,
    power: float = 0.80,
) -> int:
    """Calculate required sample size per variant for A/B test.

    Args:
        baseline_rate: Expected baseline conversion rate (0.0 to 1.0).
        minimum_detectable_effect: Minimum relative improvement to detect (e.g., 0.10 for 10%).
        confidence_level: Desired confidence level (default 0.95).
        power: Statistical power (default 0.80).

    Returns:
        Required sample size per variant.

    Notes:
        Uses approximate formula for two-proportion z-test.
    """
    if baseline_rate <= 0 or baseline_rate >= 1:
        raise ValueError("baseline_rate must be between 0 and 1 (exclusive)")

    if minimum_detectable_effect <= 0:
        raise ValueError("minimum_detectable_effect must be positive")

    # Try to import scipy for z-scores
    try:
        from scipy import stats

        alpha = 1 - confidence_level
        z_alpha = stats.norm.ppf(1 - alpha / 2)  # Two-tailed
        z_beta = stats.norm.ppf(power)
    except ImportError:
        # Use common approximations
        z_alpha = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%
        z_beta = 0.84 if power == 0.80 else 1.28  # 80% or 90%

    # Calculate test rate
    test_rate = baseline_rate * (1 + minimum_detectable_effect)
    test_rate = min(test_rate, 0.999)  # Cap at near 100%

    # Pooled rate
    p_bar = (baseline_rate + test_rate) / 2

    # Effect size (difference in proportions)
    delta = abs(test_rate - baseline_rate)

    if delta == 0:
        raise ValueError("No detectable effect size")

    # Sample size formula (per variant)
    numerator = (z_alpha + z_beta) ** 2 * (
        baseline_rate * (1 - baseline_rate) + test_rate * (1 - test_rate)
    )
    denominator = delta**2

    n = math.ceil(numerator / denominator)

    return n


def assess_test_readiness(
    current_impressions: int,
    current_conversions: int,
    baseline_rate: float | None = None,
    minimum_detectable_effect: float = 0.10,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Assess whether current data is sufficient for reliable testing.

    Args:
        current_impressions: Current impression count.
        current_conversions: Current conversion count.
        baseline_rate: Expected baseline rate (uses current if not provided).
        minimum_detectable_effect: Minimum effect to detect (default 10%).
        confidence_level: Desired confidence level.

    Returns:
        Dictionary with readiness assessment:
        {
            'is_ready': bool,
            'current_impressions': int,
            'current_conversions': int,
            'required_impressions': int,
            'required_conversions': int,
            'progress_impressions': float (0.0 to 1.0),
            'progress_conversions': float (0.0 to 1.0),
            'estimated_days_remaining': int or None,
            'recommendation': str
        }
    """
    # Use current rate if baseline not provided
    if baseline_rate is None:
        baseline_rate = (
            current_conversions / current_impressions
            if current_impressions > 0
            else 0.02  # Default 2% if no data
        )

    # Ensure baseline_rate is valid
    if baseline_rate <= 0:
        baseline_rate = 0.02
    if baseline_rate >= 1:
        baseline_rate = 0.50

    try:
        required_impressions = calculate_required_sample_size(
            baseline_rate=baseline_rate,
            minimum_detectable_effect=minimum_detectable_effect,
            confidence_level=confidence_level,
        )
    except ValueError:
        required_impressions = MIN_IMPRESSIONS

    required_impressions = max(required_impressions, MIN_IMPRESSIONS)
    required_conversions = max(
        MIN_CONVERSIONS, int(required_impressions * baseline_rate)
    )

    progress_impressions = min(1.0, current_impressions / required_impressions)
    progress_conversions = min(1.0, current_conversions / required_conversions)

    is_ready = (
        current_impressions >= required_impressions
        and current_conversions >= required_conversions
    )

    # Generate recommendation
    if is_ready:
        recommendation = "Data is sufficient for reliable statistical testing."
    elif progress_impressions < 0.5 and progress_conversions < 0.5:
        recommendation = (
            "Need significantly more data. Consider waiting longer or "
            "increasing traffic to this product."
        )
    elif progress_conversions < progress_impressions:
        recommendation = (
            "Impressions are adequate but conversions are low. "
            "May need longer test period or larger detectable effect threshold."
        )
    else:
        remaining_impressions = required_impressions - current_impressions
        recommendation = (
            f"Need approximately {remaining_impressions:,} more impressions. "
            "Continue monitoring."
        )

    return {
        "is_ready": is_ready,
        "current_impressions": current_impressions,
        "current_conversions": current_conversions,
        "required_impressions": required_impressions,
        "required_conversions": required_conversions,
        "progress_impressions": round(progress_impressions, 3),
        "progress_conversions": round(progress_conversions, 3),
        "baseline_rate": round(baseline_rate, 4),
        "minimum_detectable_effect": minimum_detectable_effect,
        "recommendation": recommendation,
    }
