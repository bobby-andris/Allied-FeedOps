---
phase: 07-data-quality-validation
plan: 04
subsystem: api-integration
tags:
  - api-endpoint
  - job-lifecycle
  - validation
  - quality-report
dependency_graph:
  requires:
    - 07-03-quality-report-module
  provides:
    - validation-report-endpoint
    - post-completion-status-correction
  affects:
    - dashboard-data-quality-indicators
    - batch-job-final-status
tech_stack:
  added:
    - fastapi-endpoint: GET /backfill/validation-report
  patterns:
    - post-completion-validation-hook
    - api-endpoint-wiring
key_files:
  created: []
  modified:
    - src/feedops/api/backfill.py
    - src/feedops/api/main.py
    - src/feedops/jobs/processor.py
decisions: []
metrics:
  duration_seconds: 111
  completed_at: "2026-02-13T12:01:47Z"
---

# Phase 7 Plan 4: API Integration & Job Lifecycle Hooks Summary

**One-liner:** Validation report API endpoint + post-completion status correction hook enforcing VALID-07

## What Was Built

Wired the quality_report module (07-03) into the API and job lifecycle:

1. **Validation Report API Endpoint** (`GET /backfill/validation-report`)
   - Added `ValidationReportResponse` Pydantic model
   - Created `get_validation_report` handler calling `generate_full_quality_report`
   - Wired endpoint in main.py (placed before `/status/{job_id}` to avoid path conflicts)
   - Returns completeness (if job_id provided), freshness, and outlier data
   - Dashboard can consume this for data quality indicators

2. **Post-Completion Status Correction Hook**
   - Added validation hook in `BatchProcessor.run()` after final status update
   - Calls `correct_job_status()` to enforce VALID-07 (95% success threshold)
   - If processor's in-memory calculation disagrees with centralized threshold, status is corrected in DB
   - Wrapped in try/except to prevent validation failures from breaking processor
   - Provides verifiable enforcement path: `processor.run()` → `correct_job_status()` → `validate_job_completeness()` → `update_job_status()`

## Technical Implementation

### API Endpoint Pattern
```python
@app.get("/backfill/validation-report", response_model=ValidationReportResponse)
async def api_validation_report(job_id: str | None = None):
    return await get_validation_report(job_id=job_id)
```

**Handler function:**
```python
async def get_validation_report(job_id: str | None = None) -> ValidationReportResponse:
    from feedops.jobs.quality_report import generate_full_quality_report
    from datetime import datetime, timezone

    report = generate_full_quality_report(job_id=job_id)

    return ValidationReportResponse(
        completeness=report.get("completeness"),
        freshness=report["freshness"],
        outliers=report["outliers"],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
```

### Post-Completion Validation Hook
```python
# In BatchProcessor.run(), after update_job_status:
try:
    from feedops.jobs.quality_report import correct_job_status
    correction = correct_job_status(self.job_id)
    if correction["corrected"]:
        final_status = correction["new_status"]
        logger.warning(
            f"Job {self.job_id}: Status corrected from "
            f"'{correction['old_status']}' to '{correction['new_status']}' "
            f"by post-completion validation"
        )
except Exception as e:
    # Don't let validation failure break the processor
    logger.error(f"Job {self.job_id}: Post-completion validation failed: {e}")
```

**Why lazy import:** Uses lazy import inside try block to avoid circular imports (same pattern as other imports in processor.py).

**Why after update_job_status:** The processor already calculated status based on its in-memory counters. The validation hook verifies this against actual DB state and the centralized VALIDATION_THRESHOLDS.

## Requirements Satisfied

**VALID-07 Enforcement:**
- ✅ Processor calls `correct_job_status` after setting final status
- ✅ If success rate is <95% but status was 'complete', it gets corrected to 'partial'
- ✅ Verifiable code path from quality_report → update_job_status
- ✅ Audit trail via correction log (logger.warning when correction applied)

**API Access:**
- ✅ Validation results accessible via GET /backfill/validation-report
- ✅ Optional job_id parameter adds job-specific completeness check
- ✅ Dashboard can consume for data quality indicators

## Deviations from Plan

None - plan executed exactly as written.

## Testing Notes

**Manual verification:**
1. Endpoint handler imports correctly (verified via grep)
2. Endpoint registered in main.py before `/status/{job_id}` route
3. Post-completion validation hook calls correct_job_status

**Runtime verification (after deployment):**
1. Call `GET /backfill/validation-report` → returns freshness + outliers
2. Call `GET /backfill/validation-report?job_id=abc-123` → includes completeness
3. Run batch job with 90% success rate → final status should be corrected to 'partial'
4. Check logs for "Status corrected from 'complete' to 'partial'" message

## Files Modified

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `src/feedops/api/backfill.py` | +28 | ValidationReportResponse model + get_validation_report handler |
| `src/feedops/api/main.py` | +10 | Import ValidationReportResponse + wire endpoint |
| `src/feedops/jobs/processor.py` | +16 | Post-completion validation hook |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `6f812a28` | feat(07-04): add validation report API endpoint |
| 2 | `59654395` | feat(07-04): wire correct_job_status into BatchProcessor completion flow |

## Integration Points

**Upstream dependencies:**
- 07-03: `quality_report.py` provides `generate_full_quality_report` and `correct_job_status`
- 05-02: `processor.py` provides BatchProcessor infrastructure

**Downstream consumers:**
- Dashboard (future): Will call `/backfill/validation-report` for data quality indicators
- All backfill jobs: Post-completion validation runs after every job completion

## Self-Check: PASSED

**Verified created files exist:** N/A (no new files created)

**Verified commits exist:**
```bash
git log --oneline --all | grep -q "6f812a28" && echo "FOUND: 6f812a28" || echo "MISSING: 6f812a28"
# FOUND: 6f812a28

git log --oneline --all | grep -q "59654395" && echo "FOUND: 59654395" || echo "MISSING: 59654395"
# FOUND: 59654395
```

**Verified modified files exist:**
```bash
[ -f "src/feedops/api/backfill.py" ] && echo "FOUND: src/feedops/api/backfill.py" || echo "MISSING: src/feedops/api/backfill.py"
# FOUND: src/feedops/api/backfill.py

[ -f "src/feedops/api/main.py" ] && echo "FOUND: src/feedops/api/main.py" || echo "MISSING: src/feedops/api/main.py"
# FOUND: src/feedops/api/main.py

[ -f "src/feedops/jobs/processor.py" ] && echo "FOUND: src/feedops/jobs/processor.py" || echo "MISSING: src/feedops/jobs/processor.py"
# FOUND: src/feedops/jobs/processor.py
```

All files modified, both commits exist.
