from __future__ import annotations

from datetime import date

from feedops.monitoring.performance_impact import (
    build_refresh_dates,
    classify_overall_label,
    compute_confidence,
    compute_diff_in_diff_lift_pct,
)


def test_build_refresh_dates_defaults_to_d_minus_1_through_d_minus_3() -> None:
    run_date = date(2026, 2, 20)

    assert build_refresh_dates(run_date, days_to_refresh=3) == [
        "2026-02-19",
        "2026-02-18",
        "2026-02-17",
    ]


def test_compute_diff_in_diff_lift_pct_uses_relative_changes() -> None:
    # treated: +20% (10 -> 12), control: +5% (8 -> 8.4), DID = +15%
    did = compute_diff_in_diff_lift_pct(
        treated_pre=10,
        treated_post=12,
        control_pre=8,
        control_post=8.4,
    )

    assert did is not None
    assert round(did, 2) == 15.00


def test_compute_diff_in_diff_lift_pct_returns_none_when_pre_is_zero() -> None:
    assert (
        compute_diff_in_diff_lift_pct(
            treated_pre=0,
            treated_post=10,
            control_pre=8,
            control_post=9,
        )
        is None
    )


def test_classify_overall_label_balanced_thresholds_positive() -> None:
    label = classify_overall_label(
        roas_did_lift_pct=8.0,
        guardrail_deltas={
            "impressions": -5.0,
            "conversions": 2.0,
            "ctr": -2.0,
            "cvr": 1.0,
        },
    )

    assert label == "positive"


def test_classify_overall_label_balanced_thresholds_negative() -> None:
    label = classify_overall_label(
        roas_did_lift_pct=-6.0,
        guardrail_deltas={
            "impressions": 1.0,
            "conversions": 0.0,
            "ctr": 0.0,
            "cvr": 0.0,
        },
    )

    assert label == "negative"


def test_classify_overall_label_blocks_positive_on_severe_guardrail_drop() -> None:
    label = classify_overall_label(
        roas_did_lift_pct=9.0,
        guardrail_deltas={
            "impressions": -20.0,
            "conversions": 1.0,
            "ctr": -1.0,
            "cvr": 1.0,
        },
    )

    assert label == "neutral"


def test_confidence_increases_with_sample_size() -> None:
    low = compute_confidence(sample_size_treated=10, sample_size_control=20, primary_effect=3.0)
    high = compute_confidence(sample_size_treated=400, sample_size_control=600, primary_effect=3.0)

    assert 0 <= low <= 1
    assert 0 <= high <= 1
    assert high > low
