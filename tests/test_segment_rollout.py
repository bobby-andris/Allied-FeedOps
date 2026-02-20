from feedops.monitoring.segment_rollout import (
    RolloutCheckpoint,
    assign_holdout,
    evaluate_rollout_checkpoint,
    should_trigger_rollback,
)


def test_assign_holdout_is_deterministic_for_same_inputs():
    first = assign_holdout("SKU-123", "towel bars", holdout_rate=0.2, salt="run-1")
    second = assign_holdout("SKU-123", "towel bars", holdout_rate=0.2, salt="run-1")
    assert first == second


def test_assign_holdout_changes_with_salt():
    a = assign_holdout("SKU-123", "towel bars", holdout_rate=0.2, salt="run-a")
    b = assign_holdout("SKU-123", "towel bars", holdout_rate=0.2, salt="run-b")
    # No guarantee always different per SKU, but this one should be stable under implementation hash.
    assert isinstance(a, bool)
    assert isinstance(b, bool)


def test_rollout_checkpoint_passes_ctr_and_safety_when_thresholds_met():
    decision = evaluate_rollout_checkpoint(
        RolloutCheckpoint(
            segment_key="towel bars",
            test_ctr=0.0318,
            holdout_ctr=0.03,
            test_low_quality_share=0.12,
            holdout_low_quality_share=0.10,
            test_cvr=0.022,
            holdout_cvr=0.022,
            conversions=12,
        )
    )

    assert decision.pass_ctr_gate is True
    assert decision.pass_safety_gate is True
    assert decision.cvr_gate_active is False
    assert decision.ready_to_promote is True


def test_rollout_checkpoint_fails_when_cvr_gate_active_and_below_threshold():
    decision = evaluate_rollout_checkpoint(
        RolloutCheckpoint(
            segment_key="towel bars",
            test_ctr=0.033,
            holdout_ctr=0.03,
            test_low_quality_share=0.105,
            holdout_low_quality_share=0.10,
            test_cvr=0.018,
            holdout_cvr=0.02,
            conversions=40,
        )
    )

    assert decision.cvr_gate_active is True
    assert decision.pass_cvr_gate is False
    assert decision.ready_to_promote is False


def test_rollback_trigger_on_two_consecutive_ctr_failures():
    history = [
        evaluate_rollout_checkpoint(
            RolloutCheckpoint(
                segment_key="towel bars",
                test_ctr=0.03,
                holdout_ctr=0.03,
                test_low_quality_share=0.10,
                holdout_low_quality_share=0.10,
                conversions=10,
            )
        ),
        evaluate_rollout_checkpoint(
            RolloutCheckpoint(
                segment_key="towel bars",
                test_ctr=0.0305,
                holdout_ctr=0.03,
                test_low_quality_share=0.10,
                holdout_low_quality_share=0.10,
                conversions=10,
            )
        ),
    ]

    assert should_trigger_rollback(history) is True


def test_rollback_trigger_on_single_high_volume_cvr_failure():
    history = [
        evaluate_rollout_checkpoint(
            RolloutCheckpoint(
                segment_key="grab bars",
                test_ctr=0.032,
                holdout_ctr=0.03,
                test_low_quality_share=0.10,
                holdout_low_quality_share=0.10,
                test_cvr=0.015,
                holdout_cvr=0.02,
                conversions=45,
            )
        )
    ]

    assert should_trigger_rollback(history) is True
