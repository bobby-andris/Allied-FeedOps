from pathlib import Path


BATCH_API_ROUTE = Path("dashboard/src/app/api/batches/route.ts")
BATCH_PUBLISH_ROUTE = Path("dashboard/src/app/api/publish/batch/route.ts")
BATCH_LIST_PAGE = Path("dashboard/src/app/(dashboard)/batches/page.tsx")
BATCH_DETAIL_PAGE = Path("dashboard/src/app/(dashboard)/batches/[batchId]/page.tsx")
BATCH_DETAIL_CLIENT = Path("dashboard/src/components/batches/BatchDetailClient.tsx")
BATCH_ASSIGNMENTS_HELPER = Path("dashboard/src/lib/batches/assignment-store.ts")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_batch_status_model_is_normalized_across_api_and_pages() -> None:
    api_source = _read(BATCH_API_ROUTE)
    list_page_source = _read(BATCH_LIST_PAGE)
    detail_page_source = _read(BATCH_DETAIL_PAGE)

    for required in ("'draft'", "'pending'", "'executing'", "'published'", "'partial'", "'failed'"):
        assert required in api_source

    assert "normalizeBatchStatus" in api_source
    assert "normalizeBatchStatus" in list_page_source
    assert "normalizeBatchStatus" in detail_page_source
    assert "status: normalizeBatchStatus(summary.status)" in list_page_source
    assert "status: normalizeBatchStatus(summary.status)" in detail_page_source
    assert ".from('publish_events')" in api_source
    assert ".from('publish_events')" in list_page_source
    assert ".from('publish_events')" in detail_page_source


def test_batch_reconciliation_prefers_assignment_and_event_state_for_readiness() -> None:
    api_source = _read(BATCH_API_ROUTE)
    list_page_source = _read(BATCH_LIST_PAGE)
    detail_page_source = _read(BATCH_DETAIL_PAGE)

    assert "deriveBatchSummary(" in api_source
    assert "deriveBatchSummary(" in list_page_source
    assert "deriveBatchSummary(" in detail_page_source
    assert "hydrateAssignmentsWithEventFailures(" in api_source
    assert "hydrateAssignmentsWithEventFailures(" in detail_page_source


def test_batch_assignment_queries_fallback_when_status_columns_missing() -> None:
    helper_source = _read(BATCH_ASSIGNMENTS_HELPER)

    assert "batch_sku_assignments" in helper_source
    assert "status, error_message" in helper_source
    assert "error.code === '42703'" in helper_source
    assert "status: null" in helper_source
    assert "error_message: null" in helper_source


def test_batch_publish_route_blocks_parallel_execution_and_sets_executing_state() -> None:
    source = _read(BATCH_PUBLISH_ROUTE)

    assert "batch_publish_already_executing" in source
    assert ".update({ status: 'executing' })" in source


def test_batch_publish_route_updates_assignment_status_and_error_reason() -> None:
    source = _read(BATCH_PUBLISH_ROUTE)

    assert ".from('batch_sku_assignments')" in source
    assert ".update({" in source
    assert "error_message" in source
    assert "status: 'pending'" in source
    assert "return 'success'" in source
    assert "return 'failed'" in source
    assert "return 'partial'" in source


def test_batch_detail_ui_exposes_failure_reason_column() -> None:
    source = _read(BATCH_DETAIL_CLIENT)

    assert "Failure Reason" in source
    assert "assignment.error_message" in source
