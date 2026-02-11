# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-11)

**Core value:** Validate Google Ads API capabilities and comprehensively map available data to inform backfill strategy before planning Phases 1-5
**Current focus:** Phase 1 - API Capability Validation

## Current Position

Phase: 1 of 4 (API Capability Validation)
Plan: 2 of 2 in current phase
Status: Phase complete
Last activity: 2026-02-12 — Completed plan 01-02 (Query Boundary and Custom Label Validation)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 2
- Average duration: 4.5 minutes
- Total execution time: 0.15 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. API Capability Validation | 2 | 9 min | 4.5 min |

**Recent Trend:**
- Latest: 01-02 (5 minutes)
- Previous: 01-01 (4 minutes)
- Trend: Consistent velocity (~4-5 min/plan)

*Updated after each plan completion*

## Accumulated Context

### Decisions

1. **search_term_view Cannot Filter by Product** (01-01, 2026-02-11)
   - API explicitly rejects `segments.product_item_id` in search_term_view queries
   - Must use campaign-join pattern (already implemented in codebase)
   - Impact: Two-step query required for product→search term association

2. **Google Ads API Uses Lowercase Offer IDs** (01-01, 2026-02-11)
   - API returns and expects `shopify_us_` format (lowercase), not `shopify_US_`
   - Database format already matches API (no transformation needed for queries)
   - Impact: Confirms existing database schema is correct; GMC publishing must still transform to uppercase

3. **LIMIT Values Up to 100K Work Without Issues** (01-02, 2026-02-12)
   - Tested 10K, 50K, and 100K LIMIT values - all succeeded with 2-4s response times
   - Recommend 50K as default batch size (balances throughput with retry granularity)
   - Impact: Can use larger batches than initially assumed, reducing total API calls needed

4. **Data Retention Starts 2020-01-01 for This Account** (01-02, 2026-02-12)
   - No data exists before 2020 despite API documentation claiming 11 years retention
   - Likely reflects account activation date, not API limitation
   - Impact: Historical backfill window is 2020-01-01 to present (~6 years)

5. **Custom Attribute Field Naming Has No Underscore** (01-02, 2026-02-12)
   - Correct: `product_custom_attribute0` through `product_custom_attribute4`
   - Incorrect: `product_custom_attribute_0` (with underscore before number)
   - Impact: Must use correct field names in all queries; research document needs correction

Key context from PROJECT.md:
- Phase 0 is discovery only — no schema migrations, no production deployment
- 5 core questions must be answered before planning main backfill
- Research validates that campaign-join pattern already exists in codebase
- GMC offer ID case sensitivity (shopify_us vs shopify_US) is known pitfall

### Pending Todos

None yet.

### Blockers/Concerns

None yet. Research summary indicates HIGH confidence in feasibility.

## Session Continuity

Last session: 2026-02-12 — Plan 01-02 execution
Stopped at: Completed Phase 1 (API Capability Validation)
Resume file: None

---
*Next step:* Phase 1 complete. Review findings and plan Phase 2 (Data Discovery)
