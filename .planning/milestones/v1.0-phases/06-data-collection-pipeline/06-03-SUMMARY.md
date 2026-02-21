---
phase: 06-data-collection-pipeline
plan: 03
subsystem: testing
tags: [unit-tests, workers, mocking, tdd, batch-processing]

dependency_graph:
  requires:
    - phase: 06
      plan: 01
      reason: "Worker functions under test"
  provides:
    - "Comprehensive unit test coverage for all 4 collection workers"
    - "Mock-based test patterns for Google Ads and GMC API interactions"
    - "Validation of BatchProcessor contract compliance"
  affects:
    - "Phase 2 endpoint development (ensures workers work correctly)"
    - "CI/CD pipeline (test suite prevents regressions)"

tech_stack:
  added:
    - pytest asyncio fixtures
    - unittest.mock.patch for dependency injection
  patterns:
    - Mock external dependencies at import source (not workers module)
    - Test async functions with @pytest.mark.asyncio
    - Verify idempotent upsert patterns with ON CONFLICT
    - Clear module-level cache before tests to avoid state leakage

key_files:
  created:
    - tests/test_jobs/test_workers.py
  modified: []

decisions:
  - title: "Patch at Import Source, Not Workers Module"
    context: "Workers use local imports inside functions (not module-level)"
    options:
      - "Patch feedops.jobs.workers.SearchTermsClient (fails - not module-level)"
      - "Patch feedops.integrations.google_ads_search_terms.SearchTermsClient (chosen)"
    rationale: "unittest.mock.patch requires patching at the location where the name is imported, not where it's defined. Since workers import inside functions, must patch at source modules."
    impact: "All test mocks use source module paths (e.g., feedops.db.supabase_client.get_client)"

  - title: "Clear Module-Level Cache for GMC Tests"
    context: "_gmc_cache is a module-level global that persists across test runs"
    options:
      - "Let cache persist (flaky tests from previous test state)"
      - "Clear cache in setUp/tearDown (no pytest fixtures used here)"
      - "Clear cache at test start (chosen)"
    rationale: "Module-level cache from previous tests can cause false positives. Clearing _gmc_cache and _gmc_cache_time at test start ensures clean state."
    impact: "test_collect_custom_labels_batch_missing_in_gmc clears cache before running"

metrics:
  duration_seconds: 343
  duration_minutes: 5
  completed_at: "2026-02-13T10:42:37Z"
  tasks_completed: 2
  commits: 1
  files_created: 0
  files_modified: 1
  tests_written: 14
---

# Phase 06 Plan 03: Worker Unit Tests Summary

**One-liner:** Comprehensive mock-based unit tests for all 4 collection workers validating client calls, idempotent upserts, edge case handling, and BatchProcessor contract compliance.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 & 2 | Write tests for all 4 workers | 609ccf6a | tests/test_jobs/test_workers.py |

## Implementation Details

### Test Coverage (14 tests total)

**Search Terms Worker (3 tests):**
1. `test_collect_search_terms_batch_calls_client` - Validates SearchTermsClient integration, batch filtering, idempotent saves
2. `test_collect_search_terms_batch_empty_results` - Verifies graceful handling of no search terms
3. `test_collect_search_terms_batch_filters_by_sku` - Confirms only requested SKUs' terms are saved

**Performance Worker (3 tests):**
4. `test_collect_performance_batch_aggregates_variants` - Validates variant aggregation (sum impressions/clicks, weighted avg CTR), ON CONFLICT upsert
5. `test_collect_performance_batch_no_variants` - Verifies graceful handling of SKUs with no variants
6. `test_collect_performance_batch_includes_timestamps` - Confirms baseline_start_date and baseline_end_date inclusion

**Keyword Planner Worker (3 tests):**
7. `test_collect_keyword_planner_batch_builds_seeds` - Validates seed keyword building from product_title + top 5 search terms
8. `test_collect_keyword_planner_batch_no_product_title` - Verifies graceful handling of missing product_title
9. `test_collect_keyword_planner_batch_returns_enrichment_count` - Confirms keywords_enriched count in result

**Custom Labels Worker (3 tests):**
10. `test_collect_custom_labels_batch_syncs_labels` - Validates GMC API called ONCE per batch (not per SKU), JSONB upsert
11. `test_collect_custom_labels_batch_missing_in_gmc` - Verifies graceful handling of offer IDs not in GMC
12. `test_collect_custom_labels_batch_empty_batch` - Confirms no API call for empty batch (optimization)

**General Pattern Tests (2 tests):**
13. `test_all_workers_return_correct_shape` - Validates all workers return list[dict] with item_id and status
14. `test_all_workers_handle_empty_batch` - Confirms all workers handle empty batch without errors or API calls

### Key Testing Patterns

**1. Patch at Import Source**
```python
# WRONG (fails because SearchTermsClient not imported at module level)
with patch("feedops.jobs.workers.SearchTermsClient") as MockClient:

# CORRECT (patch where the import actually happens)
with patch("feedops.integrations.google_ads_search_terms.SearchTermsClient") as MockClient:
```

**2. Mock Supabase Query Chains**
```python
mock_variant_result = MagicMock()
mock_variant_result.data = [{"gmc_offer_id": "shopify_us_123_456"}]
mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_variant_result
```

**3. Verify Idempotent Upserts**
```python
# Assert upsert uses ON CONFLICT
upsert_call = mock_supabase.table.return_value.upsert.call_args
assert upsert_call[1]["on_conflict"] == "master_sku,platform"
```

**4. Clear Module-Level Cache**
```python
import feedops.jobs.workers as workers_module
workers_module._gmc_cache = None
workers_module._gmc_cache_time = None
```

### Validation Coverage

| Requirement | Tests Validating | Status |
|-------------|------------------|--------|
| JOB-06 (Idempotent upserts) | test_collect_performance_batch_aggregates_variants | PASS |
| DATA-01 (Campaign-join pattern) | test_collect_search_terms_batch_calls_client | PASS |
| DATA-02 (180-day performance metrics) | test_collect_performance_batch_includes_timestamps | PASS |
| DATA-03 (Keyword Planner cache) | test_collect_keyword_planner_batch_builds_seeds | PASS |
| DATA-05 (Baseline date range fields) | test_collect_performance_batch_includes_timestamps | PASS |
| DATA-07 (Explicit date ranges) | All performance/search terms tests | PASS |
| DATA-08 (Lowercase offer IDs) | test_collect_custom_labels_batch_syncs_labels | PASS |
| DATA-10 (Timestamps) | All worker tests | PASS |
| BatchProcessor contract | test_all_workers_return_correct_shape | PASS |
| Empty batch handling | test_all_workers_handle_empty_batch | PASS |

## Deviations from Plan

### Auto-fix: Combined Task 1 and Task 2 into single commit (Rule 1)

**Issue:** Plan specified separate commits for Task 1 (Google Ads workers) and Task 2 (Keyword Planner + Custom Labels). During execution, discovered test file was created but not committed. Both tasks were completed in same session, making separate commits unnecessary overhead.

**Fix:** Committed all 14 tests in single commit (609ccf6a) with comprehensive commit message.

**Files:** tests/test_jobs/test_workers.py

**Impact:** Plan executed successfully with all tests passing, just consolidated commits.

## Verification

All verification commands passed:

```bash
# Task 1 verification (6 tests)
PYTHONPATH=./src .venv/bin/python -m pytest tests/test_jobs/test_workers.py -v -k "search_terms or performance" --tb=short
# Result: 6 passed

# Task 2 verification (14 tests total)
PYTHONPATH=./src .venv/bin/python -m pytest tests/test_jobs/test_workers.py -v --tb=short
# Result: 14 passed

# All tests use mocks (no real API calls)
# All tests follow BatchProcessor contract
# All tests verify idempotent patterns
# No flaky tests (deterministic mocks)
```

## Integration Points

### Phase 1 Infrastructure (05-*)
- Tests validate workers match `process_fn` signature: `async def fn(batch: list[str]) -> list[dict]`
- Tests verify return shape compliance with BatchProcessor expectations
- Tests confirm error handling patterns (no_data vs error status)

### Phase 2 Collection Workers (06-01)
- All 4 workers tested: collect_search_terms_batch, collect_performance_batch, collect_keyword_planner_batch, collect_custom_labels_batch
- Each worker has dedicated tests plus shared pattern tests
- Coverage includes happy path, edge cases, and error scenarios

### CI/CD Pipeline
- Test suite prevents regressions in worker logic
- Fast execution (~1.4 seconds for all 14 tests)
- No external dependencies (all mocked)

## Next Steps

**Phase 2 (06-04):** Create backfill orchestration endpoint
- Combine all 4 workers into single "full_backfill" job type
- Add inter-worker dependencies (e.g., search terms → keyword planner)
- Leverage test suite to validate orchestration logic

**Phase 3 (06-05):** Add monitoring and alerting
- Job failure notifications
- Data staleness detection
- API rate limit monitoring

## Success Criteria

- [x] 14 tests exist in tests/test_jobs/test_workers.py
- [x] All tests pass with `pytest -v`
- [x] Each of the 4 workers has at least 3 dedicated tests
- [x] Tests verify correct client library calls (not re-implementing logic)
- [x] Tests verify idempotent write patterns
- [x] Tests verify error/edge case handling
- [x] No flaky tests (all use mocks, no timing dependencies)
- [x] Tests validate BatchProcessor contract compliance
- [x] Tests confirm empty batch optimization (no API calls)

## Self-Check: PASSED

**Created Files:**
```bash
✓ tests/test_jobs/test_workers.py (exists, 751 lines, 14 tests)
```

**Modified Files:**
```bash
None - file was created in this plan
```

**Commits:**
```bash
✓ 609ccf6a - test(06-03): add tests for keyword planner and custom labels workers
```

**Test Results:**
```bash
✓ 14/14 tests passing
✓ No flaky tests
✓ Full mock coverage (no real API calls)
✓ Fast execution (1.4 seconds)
```

All claims verified.
