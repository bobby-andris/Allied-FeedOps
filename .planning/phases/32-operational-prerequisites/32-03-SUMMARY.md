---
plan: 32-03
title: Backfill + Phase Gate Validation Script
status: complete
started: 2026-02-25
completed: 2026-02-25
---

## What Was Built

Backfilled 30 days of `funnel_snapshots_daily` data (3,953 rows, Jan 26 – Feb 24) via the existing backfill endpoint running against localhost. Created `scripts/validate_phase32.py` — a standalone validation script that checks all 3 Phase 32 success criteria via Supabase REST API.

## Key Files

### Created
- `scripts/validate_phase32.py` — Phase gate validation (3 SQL checks, PASS/FAIL output, exit code 0/1)

### Modified
- (none — backfill used existing endpoint)

## Decisions Made
- Used PostgREST column probing (`SELECT col LIMIT 0`) instead of `information_schema` queries — avoids need for RPC function or management API access
- Zero external dependencies — uses only `urllib` from stdlib
- Reads env vars with fallbacks: `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Deviations
- None

## Self-Check: PASSED
- [x] Backfill endpoint returned 3,953 rows across 30 days
- [x] Zero days with errors (all returned 117-142 rows)
- [x] Validation script runs all 3 checks: OPS-01 PASS, OPS-03 PASS, OPS-04 PASS
- [x] Script exits 0 on all pass
