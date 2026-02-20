from feedops.cli.main import (
    _classify_missing_label_queue,
    _compute_reconcile_coverage_metrics,
)


def test_classify_queue_marks_gmc_present_blank_as_expected_catchall() -> None:
    assert (
        _classify_missing_label_queue(exists_in_gmc=True, treat_gmc_blank_as_catchall=True)
        == "queue_b_expected_catchall_blank"
    )


def test_classify_queue_preserves_upstream_label_mode_when_catchall_disabled() -> None:
    assert (
        _classify_missing_label_queue(exists_in_gmc=True, treat_gmc_blank_as_catchall=False)
        == "queue_b_blank_label_upstream"
    )


def test_compute_reconcile_coverage_metrics_separates_strict_and_actionable() -> None:
    metrics = _compute_reconcile_coverage_metrics(
        offer_linked_total=100,
        missing_total=10,
        queue_a_missing_offer_mapping=2,
        queue_b_expected_catchall_blank=8,
        treat_gmc_blank_as_catchall=True,
    )

    assert metrics["strict_label_coverage_pct"] == 90.0
    assert metrics["actionable_coverage_pct"] == 98.0


def test_compute_reconcile_coverage_metrics_includes_queue_b_in_strict_mode() -> None:
    metrics = _compute_reconcile_coverage_metrics(
        offer_linked_total=100,
        missing_total=10,
        queue_a_missing_offer_mapping=2,
        queue_b_expected_catchall_blank=8,
        treat_gmc_blank_as_catchall=False,
    )

    assert metrics["strict_label_coverage_pct"] == 90.0
    assert metrics["actionable_coverage_pct"] == 90.0
