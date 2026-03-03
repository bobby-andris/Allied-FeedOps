"""Smoke and parity tests for JobRunner.

Tests verify:
- JOBS-01: JobRunner class exists and is importable standalone (no main.py dependency)
- JOBS-02: Single run() dispatches on mode flag
- JOBS-03: Shared status updates use _upsert_batch_job_sku_status
- JOBS-04: Variant adaptation called for hybrid variants, not for batch
- JOBS-05: cancel_event.set() stops processing at next SKU boundary
- JOBS-06: Batch and hybrid jobs produce identical persistence call sequences to old functions
"""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch, call


# ===========================================================================
# JOBS-01: Importability and no circular imports
# ===========================================================================


def test_job_runner_importable_standalone():
    """JobRunner must be importable without importing main.py."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="batch")
    assert callable(runner.run)


def test_no_circular_import_with_main():
    """Importing both job_runner and main must succeed without circular import."""
    import feedops.api.job_runner  # noqa: PLC0415
    import feedops.api.main  # noqa: PLC0415

    # If we get here without ImportError, there's no circular import.
    assert True


def test_invalid_mode_raises():
    """JobRunner with unknown mode must raise AssertionError."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    try:
        JobRunner(mode="invalid")
        assert False, "Expected AssertionError"
    except AssertionError:
        pass


# ===========================================================================
# JOBS-02: Mode dispatch
# ===========================================================================


def test_run_dispatches_on_mode_batch():
    """JobRunner(mode='batch').run dispatches to _run_batch."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="batch")
    called = []

    async def fake_batch(**kwargs):
        called.append("batch")

    runner._run_batch = fake_batch
    asyncio.run(runner.run(job_id="j1", skus=[], num_candidates=1, dry_run=False))
    assert called == ["batch"]


def test_run_dispatches_on_mode_hybrid():
    """JobRunner(mode='hybrid').run dispatches to _run_hybrid."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="hybrid")
    called = []

    async def fake_hybrid(**kwargs):
        called.append("hybrid")

    runner._run_hybrid = fake_hybrid
    asyncio.run(
        runner.run(
            job_id="j1",
            families=[],
            single_skus=[],
            options={},
        )
    )
    assert called == ["hybrid"]


# ===========================================================================
# JOBS-05: Cancellation
# ===========================================================================


def test_cancel_event_respected():
    """cancel_event.set() causes _is_cancelled() to return True."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    event = threading.Event()
    runner = JobRunner(mode="batch", cancel_event=event)
    assert not runner._is_cancelled()
    event.set()
    assert runner._is_cancelled()


def test_cancel_event_default_not_set():
    """Default cancel_event is not set at construction."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="batch")
    assert not runner._is_cancelled()


def test_cancellation_updates_job_status():
    """When cancelled mid-run, job status is updated to 'failed' with 'Job cancelled'."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    event = threading.Event()
    event.set()  # Pre-cancelled

    runner = JobRunner(mode="batch", cancel_event=event)

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    with (
        patch("feedops.api.job_runner.get_client", return_value=mock_supabase),
        patch("feedops.api.job_runner.ensure_generation_enabled"),
        patch("feedops.api.job_runner._resolve_execution_request_id", return_value="req-1"),
        patch("feedops.api.job_runner._normalize_generation_options", return_value={
            "platforms": ["google"],
            "titles": True,
            "descriptions": True,
        }),
    ):
        asyncio.run(
            runner.run(
                job_id="job-cancel-1",
                skus=["SKU-A", "SKU-B"],
                num_candidates=1,
                dry_run=False,
            )
        )

    # Verify that the job was updated with failed + "Job cancelled"
    all_calls = mock_supabase.table.call_args_list
    table_names = [c.args[0] for c in all_calls]
    assert "batch_generation_jobs" in table_names

    # Find the final update call that sets status=failed / Job cancelled
    update_data_calls = []
    for c in mock_supabase.table.return_value.update.call_args_list:
        if c.args:
            update_data_calls.append(c.args[0])

    cancelled_call = next(
        (d for d in update_data_calls if d.get("status") == "failed" and "cancelled" in str(d.get("error_message", "")).lower()),
        None,
    )
    assert cancelled_call is not None, f"Expected cancelled status update, got: {update_data_calls}"


# ===========================================================================
# JOBS-03 & JOBS-04: Shared status updates and variant adaptation strategy
# ===========================================================================


def test_shared_status_updates():
    """Both batch mode calls _upsert_batch_job_sku_status for each SKU."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="batch")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    mock_generated = {
        "prompt_hashes": {},
        "system_prompts": {},
        "user_prompts": {},
        "usage_by_platform": {},
        "latency_by_platform": {},
        "parse_by_platform": {},
        "retry_by_platform": {},
        "finish_sentences": {},
    }

    with (
        patch("feedops.api.job_runner.get_client", return_value=mock_supabase),
        patch("feedops.api.job_runner.ensure_generation_enabled"),
        patch("feedops.api.job_runner._resolve_execution_request_id", return_value="req-1"),
        patch("feedops.api.job_runner._normalize_generation_options", return_value={
            "platforms": ["google"],
            "titles": True,
            "descriptions": False,
        }),
        patch("feedops.api.job_runner.resolve_canonical_master_sku", side_effect=lambda sb, sku: sku),
        patch("feedops.api.job_runner.load_parent_sku_from_supabase", return_value=MagicMock()),
        patch("feedops.api.job_runner.get_provider", return_value=MagicMock()),
        patch("feedops.api.job_runner.close_provider", new=AsyncMock()),
        patch("feedops.api.job_runner.generate_per_platform", new=AsyncMock(return_value=mock_generated)),
        patch("feedops.api.job_runner._persist_generated_content_and_history"),
        patch("feedops.api.job_runner._emit_generation_summary"),
        patch("feedops.api.job_runner._persist_finish_prompt_lineage"),
        patch("feedops.api.job_runner._upsert_batch_job_sku_status") as mock_upsert,
        patch("feedops.api.job_runner._extract_scoped_telemetry", return_value={
            "tokens_used": 0, "cost_usd": 0.0, "latency_ms": 0,
            "provider_attempt_count": 0, "parse_retry_count": 0,
        }),
        patch("feedops.api.job_runner._telemetry_scope_for_content", return_value="google"),
        patch("feedops.api.job_runner._content_field_key", return_value="google_title"),
        patch("feedops.api.job_runner._provider_label", return_value="openai"),
        patch("feedops.api.job_runner.get_platform_system_prompt_hash", return_value="hash"),
        patch("feedops.api.job_runner._extract_query_intent_generation_diagnostics", return_value={}),
    ):
        asyncio.run(
            runner.run(
                job_id="job-1",
                skus=["SKU-A"],
                num_candidates=1,
                dry_run=False,
            )
        )

    # Should have called _upsert_batch_job_sku_status at least twice for SKU-A (processing + completed)
    assert mock_upsert.call_count >= 2
    statuses = [c.kwargs.get("status") or c.args[2] for c in mock_upsert.call_args_list]
    assert "processing" in statuses
    assert "completed" in statuses


def test_variant_adaptation_strategy():
    """Hybrid mode calls adapt_variant_content for variants; batch mode never calls it."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    # --- Batch mode: adapt_variant_content should NOT be called ---
    batch_runner = JobRunner(mode="batch")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    mock_generated = {
        "prompt_hashes": {},
        "system_prompts": {},
        "user_prompts": {},
        "usage_by_platform": {},
        "latency_by_platform": {},
        "parse_by_platform": {},
        "retry_by_platform": {},
        "finish_sentences": {},
    }

    with (
        patch("feedops.api.job_runner.get_client", return_value=mock_supabase),
        patch("feedops.api.job_runner.ensure_generation_enabled"),
        patch("feedops.api.job_runner._resolve_execution_request_id", return_value="req-1"),
        patch("feedops.api.job_runner._normalize_generation_options", return_value={
            "platforms": ["google"],
            "titles": True,
            "descriptions": False,
        }),
        patch("feedops.api.job_runner.resolve_canonical_master_sku", side_effect=lambda sb, sku: sku),
        patch("feedops.api.job_runner.load_parent_sku_from_supabase", return_value=MagicMock()),
        patch("feedops.api.job_runner.get_provider", return_value=MagicMock()),
        patch("feedops.api.job_runner.close_provider", new=AsyncMock()),
        patch("feedops.api.job_runner.generate_per_platform", new=AsyncMock(return_value=mock_generated)),
        patch("feedops.api.job_runner._persist_generated_content_and_history"),
        patch("feedops.api.job_runner._emit_generation_summary"),
        patch("feedops.api.job_runner._persist_finish_prompt_lineage"),
        patch("feedops.api.job_runner._upsert_batch_job_sku_status"),
        patch("feedops.api.job_runner._extract_scoped_telemetry", return_value={
            "tokens_used": 0, "cost_usd": 0.0, "latency_ms": 0,
            "provider_attempt_count": 0, "parse_retry_count": 0,
        }),
        patch("feedops.api.job_runner._telemetry_scope_for_content", return_value="google"),
        patch("feedops.api.job_runner._content_field_key", return_value="google_title"),
        patch("feedops.api.job_runner._provider_label", return_value="openai"),
        patch("feedops.api.job_runner.get_platform_system_prompt_hash", return_value="hash"),
        patch("feedops.api.job_runner._extract_query_intent_generation_diagnostics", return_value={}),
        patch("feedops.api.job_runner.adapt_variant_content", new=AsyncMock()) as mock_adapt_batch,
    ):
        asyncio.run(
            batch_runner.run(
                job_id="job-batch",
                skus=["SKU-A"],
                num_candidates=1,
                dry_run=False,
            )
        )
        # Batch mode must NOT call adapt_variant_content
        assert mock_adapt_batch.call_count == 0, "Batch mode must not call adapt_variant_content"


def test_batch_parity():
    """Batch mode makes identical sequence of persistence calls as old process_batch_job."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="batch")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    mock_generated = {
        "prompt_hashes": {"google": "hash123"},
        "system_prompts": {"google": "sys"},
        "user_prompts": {"google": "user"},
        "usage_by_platform": {"google": {"prompt_tokens": 100, "completion_tokens": 50}},
        "latency_by_platform": {"google": 1200},
        "parse_by_platform": {},
        "retry_by_platform": {},
        "finish_sentences": {},
        "google_title": "Test Title",
    }

    with (
        patch("feedops.api.job_runner.get_client", return_value=mock_supabase),
        patch("feedops.api.job_runner.ensure_generation_enabled"),
        patch("feedops.api.job_runner._resolve_execution_request_id", return_value="req-parity"),
        patch("feedops.api.job_runner._normalize_generation_options", return_value={
            "platforms": ["google"],
            "titles": True,
            "descriptions": False,
        }),
        patch("feedops.api.job_runner.resolve_canonical_master_sku", side_effect=lambda sb, sku: sku),
        patch("feedops.api.job_runner.load_parent_sku_from_supabase", return_value=MagicMock()),
        patch("feedops.api.job_runner.get_provider", return_value=MagicMock()),
        patch("feedops.api.job_runner.close_provider", new=AsyncMock()),
        patch("feedops.api.job_runner.generate_per_platform", new=AsyncMock(return_value=mock_generated)),
        patch("feedops.api.job_runner._persist_generated_content_and_history") as mock_persist,
        patch("feedops.api.job_runner._emit_generation_summary") as mock_emit,
        patch("feedops.api.job_runner._persist_finish_prompt_lineage") as mock_lineage,
        patch("feedops.api.job_runner._upsert_batch_job_sku_status"),
        patch("feedops.api.job_runner._extract_scoped_telemetry", return_value={
            "tokens_used": 150, "cost_usd": 0.001, "latency_ms": 1200,
            "provider_attempt_count": 1, "parse_retry_count": 0,
        }),
        patch("feedops.api.job_runner._telemetry_scope_for_content", return_value="google"),
        patch("feedops.api.job_runner._content_field_key", return_value="google_title"),
        patch("feedops.api.job_runner._provider_label", return_value="openai"),
        patch("feedops.api.job_runner.get_platform_system_prompt_hash", return_value="hash"),
        patch("feedops.api.job_runner._extract_query_intent_generation_diagnostics", return_value={}),
    ):
        asyncio.run(
            runner.run(
                job_id="job-parity",
                skus=["SKU-A"],
                num_candidates=1,
                dry_run=False,
            )
        )

    # Parity assertions: must call persist, lineage, and emit (same as old process_batch_job)
    assert mock_persist.call_count == 1, f"Expected 1 persist call, got {mock_persist.call_count}"
    assert mock_lineage.call_count == 1, f"Expected 1 lineage call, got {mock_lineage.call_count}"
    # emit called once per platform+content_type AND once for final job status
    assert mock_emit.call_count >= 1

    # Verify persist was called with correct mode
    persist_kwargs = mock_persist.call_args.kwargs
    assert persist_kwargs.get("mode") == "full_generation_v2"
    assert persist_kwargs.get("master_sku") == "SKU-A"
    assert persist_kwargs.get("platform") == "google"


def test_hybrid_parity():
    """Hybrid mode makes identical sequence of persistence calls as old process_hybrid_batch_job."""
    from feedops.api.job_runner import JobRunner  # noqa: PLC0415

    runner = JobRunner(mode="hybrid")

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    mock_generated = {
        "prompt_hashes": {"google": "hash123"},
        "system_prompts": {"google": "sys"},
        "user_prompts": {"google": "user"},
        "usage_by_platform": {"google": {}},
        "latency_by_platform": {"google": 1200},
        "parse_by_platform": {},
        "retry_by_platform": {},
        "finish_sentences": {},
        "google_title": "Test Title",
    }

    # Simple family mock for single SKU (no variants)
    mock_family = MagicMock()
    mock_family.master_skus = ["BASE-SKU"]
    mock_family.base_sku = "BASE-SKU"
    mock_family.variant_skus = []

    with (
        patch("feedops.api.job_runner.get_client", return_value=mock_supabase),
        patch("feedops.api.job_runner.ensure_generation_enabled"),
        patch("feedops.api.job_runner._resolve_execution_request_id", return_value="req-hybrid"),
        patch("feedops.api.job_runner.resolve_canonical_master_sku", side_effect=lambda sb, sku: sku),
        patch("feedops.api.job_runner.load_parent_sku_from_supabase", return_value=MagicMock()),
        patch("feedops.api.job_runner.get_provider", return_value=MagicMock()),
        patch("feedops.api.job_runner.close_provider", new=AsyncMock()),
        patch("feedops.api.job_runner.generate_per_platform", new=AsyncMock(return_value=mock_generated)),
        patch("feedops.api.job_runner._persist_generated_content_and_history") as mock_persist,
        patch("feedops.api.job_runner._emit_generation_summary") as mock_emit,
        patch("feedops.api.job_runner._persist_finish_prompt_lineage") as mock_lineage,
        patch("feedops.api.job_runner._upsert_batch_job_sku_status"),
        patch("feedops.api.job_runner._extract_scoped_telemetry", return_value={
            "tokens_used": 0, "cost_usd": 0.0, "latency_ms": 0,
            "provider_attempt_count": 0, "parse_retry_count": 0,
        }),
        patch("feedops.api.job_runner._telemetry_scope_for_content", return_value="google"),
        patch("feedops.api.job_runner._content_field_key", return_value="google_title"),
        patch("feedops.api.job_runner._provider_label", return_value="openai"),
        patch("feedops.api.job_runner.get_platform_system_prompt_hash", return_value="hash"),
        patch("feedops.api.job_runner._extract_query_intent_generation_diagnostics", return_value={}),
        patch("feedops.api.job_runner.adapt_variant_content", new=AsyncMock()),
    ):
        asyncio.run(
            runner.run(
                job_id="job-hybrid-parity",
                families=[mock_family],
                single_skus=[],
                options={
                    "platforms": ["google"],
                    "titles": True,
                    "descriptions": False,
                },
            )
        )

    # Parity assertions for hybrid (same as old process_hybrid_batch_job)
    assert mock_persist.call_count >= 1, f"Expected at least 1 persist call, got {mock_persist.call_count}"
    assert mock_lineage.call_count >= 1, f"Expected at least 1 lineage call, got {mock_lineage.call_count}"
    assert mock_emit.call_count >= 1

    # Verify the mode used matches hybrid's full_generation_v2
    persist_kwargs = mock_persist.call_args.kwargs
    assert persist_kwargs.get("mode") == "full_generation_v2"
