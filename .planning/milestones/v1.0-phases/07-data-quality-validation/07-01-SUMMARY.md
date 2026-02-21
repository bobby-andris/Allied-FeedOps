---
phase: 07-data-quality-validation
plan: 01
subsystem: data-collection-validation
tags: [validation, pydantic, data-quality, workers]
dependency_graph:
  requires: [phase-06-data-collection-pipeline]
  provides: [data-validation-models, pre-write-validation]
  affects: [workers.py, future-monitoring-tasks]
tech_stack:
  added: [pydantic-validation-models]
  patterns: [field-validators, cross-field-validation, type-coercion]
key_files:
  created:
    - src/feedops/jobs/validators.py
  modified:
    - src/feedops/jobs/workers.py
decisions:
  - title: "Type Coercion Enabled"
    rationale: "ConfigDict(strict=False) allows API responses with numeric types (int/float) to be coerced, preventing validation failures on valid data with minor type mismatches"
    impact: "More robust validation - accepts 100 or 100.0 for numeric fields"
  - title: "Validation Errors as Item-Level Status"
    rationale: "Invalid records produce 'validation_error' status (not batch-level exceptions), allowing batch processing to continue"
    impact: "Resilient batch processing - one bad record doesn't block entire batch"
  - title: "Light Validation for Supplementary Data"
    rationale: "Keyword Planner and Custom Labels use non-blocking validation (warnings only) since they're supplementary to core metrics"
    impact: "Core metrics strictly enforced, supplementary data logs warnings"
metrics:
  duration_minutes: 2.4
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  commits: 2
  completed_date: 2026-02-13
---

# Phase 07 Plan 01: Data Validation Foundation Summary

**One-liner:** Pydantic validation models with CTR 0-1 and clicks <= impressions constraints integrated into all 4 data collection workers as pre-write gates

## What Was Built

Created comprehensive validation layer for data collection pipeline:

1. **validators.py**: 4 Pydantic models with field constraints and cross-field validators
2. **Updated workers.py**: All 4 workers validate data before database writes
3. **VALIDATION_THRESHOLDS**: Configurable constants for freshness/success thresholds

## Validation Rules Enforced

**VALID-05 (Non-Empty/Non-Negative)**:
- All string fields: min_length=1
- All numeric fields: ge=0.0 or ge=0

**VALID-06 (Logical Constraints)**:
- `avg_ctr`: 0.0 to 1.0
- `avg_cvr`: 0.0 to 1.0
- `avg_clicks <= avg_impressions` (cross-field validator)
- `clicks <= impressions` for search terms (cross-field validator)

**VALID-09 (Date Ranges)**:
- `baseline_end_date > baseline_start_date` (cross-field validator)

## Integration Patterns

**Performance Metrics (Strict)**:
```python
validated = ValidatedPerformanceMetrics(**baseline_record)
supabase.table("performance_baselines").upsert(
    validated.model_dump(exclude_none=True),
    on_conflict="master_sku,platform"
).execute()
```
- Validation failure produces `{"status": "validation_error", "error": str(e)}`
- Invalid records NOT written to database

**Search Terms (Filter)**:
```python
validated_terms = []
for term in filtered_terms:
    try:
        ValidatedSearchTerm(...)
        validated_terms.append(term)
    except ValidationError:
        logger.warning(...)
```
- Invalid terms filtered out
- Only validated terms saved to database

**Keyword Planner / Custom Labels (Non-Blocking)**:
- Validation runs post-fetch/pre-update
- Logs warnings for invalid entries
- Doesn't block batch (supplementary data)

## Deviations from Plan

None - plan executed exactly as written.

## Validation Examples

**Rejects Invalid Data**:
```python
# avg_clicks > avg_impressions
ValidatedPerformanceMetrics(
    avg_impressions=100, avg_clicks=200, ...
)
# ValidationError: avg_clicks (200.0) cannot exceed avg_impressions (100.0)

# avg_ctr > 1.0
ValidatedPerformanceMetrics(avg_ctr=1.5, ...)
# ValidationError: Input should be less than or equal to 1.0

# Empty query text
ValidatedSearchTerm(query_text="", ...)
# ValidationError: String should have at least 1 character
```

**Accepts Valid Data**:
```python
ValidatedPerformanceMetrics(
    master_sku="WP-2/16-GAL",
    platform="google",
    avg_impressions=1000.0,
    avg_clicks=50.0,
    avg_ctr=0.05,
    avg_conversions=2.0,
    avg_conversion_value=150.0,
    avg_cvr=0.04,
    avg_cost=25.0,
    avg_roas=6.0,
    baseline_start_date="2025-01-01",
    baseline_end_date="2025-06-30",
)
# ✓ Valid
```

## VALIDATION_THRESHOLDS Constants

```python
VALIDATION_THRESHOLDS = {
    "baseline_freshness_days": 60,      # Phase 07-03 uses this
    "search_terms_freshness_days": 7,   # Phase 07-03 uses this
    "keyword_cache_ttl_days": 30,       # Phase 07-03 uses this
    "job_success_threshold": 0.95,      # Phase 07-03 VALID-07 requirement
}
```

Used by Plan 07-03 for monitoring/alerting rules.

## Files Created

**src/feedops/jobs/validators.py** (163 lines):
- `ValidatedPerformanceMetrics`: 12 numeric fields + 2 date fields + 2 validators
- `ValidatedSearchTerm`: 4 fields + 1 validator
- `ValidatedKeywordMetrics`: 4 fields (optional competition metrics)
- `ValidatedCustomLabels`: gmc_offer_id + custom_labels dict
- `VALIDATION_THRESHOLDS`: Shared constants for Phase 07-03

## Files Modified

**src/feedops/jobs/workers.py** (+70 lines):
- Imports: `ValidatedPerformanceMetrics`, `ValidatedSearchTerm`, `ValidatedKeywordMetrics`, `ValidatedCustomLabels`, `ValidationError`
- `collect_performance_batch`: Validate before upsert, return `validation_error` status on failure
- `collect_search_terms_batch`: Filter out invalid terms pre-save
- `collect_keyword_planner_batch`: Validate post-fetch, log warnings
- `collect_custom_labels_batch`: Validate pre-update, skip invalid

## Testing

**Import Test**:
```bash
python -c "from feedops.jobs.validators import *"
# ✓ All models imported successfully
```

**Validation Test**:
```bash
python -c "ValidatedPerformanceMetrics(avg_clicks=200, avg_impressions=100, ...)"
# ✓ PASS: Rejected invalid data (clicks > impressions)
```

**Worker Integration Test**:
```bash
python -c "from feedops.jobs.workers import *"
# ✓ All workers import successfully with validators
```

**Grep Test**:
```bash
grep -n "Validated*" src/feedops/jobs/workers.py
# ✓ Found validators in all 4 workers
```

## Commits

1. **2c985621** - `feat(07-01): create Pydantic validation models for data collection`
   - Created validators.py with 4 models + VALIDATION_THRESHOLDS
   - Implements VALID-05, VALID-06, VALID-09

2. **5a4d06c4** - `feat(07-01): integrate validation into data collection workers`
   - Updated all 4 workers with pre-write validation
   - Invalid records produce validation_error status (not crashes)

## Self-Check: PASSED

**Files exist**:
```bash
[ -f "src/feedops/jobs/validators.py" ] && echo "FOUND: src/feedops/jobs/validators.py"
# ✓ FOUND: src/feedops/jobs/validators.py
```

**Commits exist**:
```bash
git log --oneline --all | grep -q "2c985621" && echo "FOUND: 2c985621"
# ✓ FOUND: 2c985621

git log --oneline --all | grep -q "5a4d06c4" && echo "FOUND: 5a4d06c4"
# ✓ FOUND: 5a4d06c4
```

**Validators referenced in workers**:
```bash
grep "ValidatedPerformanceMetrics\|ValidatedSearchTerm" src/feedops/jobs/workers.py
# ✓ Found in imports and usage (lines 42-45, 122, 331, 466, 607)
```

## Next Steps

**Phase 07 Plan 02**: Create validation test suite
- Unit tests for each validator model
- Integration tests for worker validation flows
- Test cases for edge cases (0 clicks, 0 impressions, etc.)

**Phase 07 Plan 03**: Implement monitoring and alerting
- Uses `VALIDATION_THRESHOLDS["job_success_threshold"]` for VALID-07
- Freshness monitoring using threshold constants
- Dashboard for validation error tracking
