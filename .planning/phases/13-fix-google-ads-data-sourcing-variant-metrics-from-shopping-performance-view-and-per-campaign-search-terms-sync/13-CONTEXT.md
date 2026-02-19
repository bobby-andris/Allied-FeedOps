# Phase 13: Fix Google Ads Data Sourcing - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix how Google Ads data is fetched and stored in the system — two specific issues:
1. Variant-level performance metrics must come from `shopping_performance_view`
2. Search terms must sync using the per-campaign join pattern

This phase covers: diagnosing the root cause, fixing the Python pipeline code, cleaning up bad data, and re-syncing all 2,784 SKUs with correct data. New features (new metrics, new pages, new APIs) are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Root cause investigation (Plan 1)
- Phase starts with a diagnosis step **before any fix code is written**
- Goal: code trace + process retrospective — how did this diverge from Phase 0 research and the Phase 6 implementation?
- Empirical confirmation required: query current `search_queries` for a published SKU, re-run the correct API logic, compare results to prove the bug exists in data (not just theory)
- Produce a **13-DIAGNOSIS.md** file with findings: what's wrong in code, why Phase 0/6/7 didn't catch it, what the fix addresses
- Use the 36 published SKUs as test subjects throughout (they have the most data for comparison)

### Backfill scope
- **All 2,784 SKUs** get re-synced after the fix (not just published, not just priority)
- **180 days** of historical data (matches the original v1.0 backfill window)
- Use **existing backfill job infrastructure** (batch processor + job tracking from Phase 1/2) — resumable, progress visible in /monitoring
- Phase is not complete until corrected data is in the database — triggering re-sync is part of the phase deliverables

### Existing data handling
- **search_queries**: delete and re-insert (clean slate approach)
  - Per-SKU delete right before re-inserting that SKU (not a full table wipe)
  - Safe for resume: if job fails mid-way, only processed SKUs are cleared
  - Add **synced_at timestamp** to search_queries rows to distinguish corrected data from old data
- **performance_baselines / performance_snapshots**: defer decision — diagnosis step must confirm whether these are affected before deciding to re-capture

### Sync trigger
- **One-time re-sync**: manual API call to existing backfill endpoint (`POST /backfill/start`) after deploy
  - No new endpoint needed — use existing job infrastructure
  - Triggered once after confirming the fix looks correct
- **Ongoing**: daily Cloud Scheduler incremental sync picks up the fix automatically (same code path, no extra wiring)
- **Notification**: use existing Slack webhook — job completion notification fires through normal job lifecycle

### Success definition
- Verify **both** Search Insights page and Performance page show improved/corrected data
- **SQL verification**: confirm row counts changed and new `synced_at` timestamps exist for re-synced SKUs
- **Dashboard visual check**: Search Insights shows richer query data; Performance shows correct variant-level metrics
- Test/validation subject: the 36 published SKUs (have performance snapshots, most data available for comparison)

### Claude's Discretion
- Which specific published SKU(s) to use as the primary test subject during development
- Internal structure of 13-DIAGNOSIS.md
- Whether to add a DB index on `synced_at` if query patterns benefit from it
- Exact SQL for the per-SKU delete (whether to key on `master_sku`, `gmc_offer_id`, or both)

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants a process retrospective alongside the code trace — Phase 0 did extensive Google Ads API research and Phases 1-8 focused on exactly this data retrieval. The investigation should explain why the campaign-join pattern (documented in Phase 0) ended up implemented incorrectly or incompletely.
- The 13-DIAGNOSIS.md should be honest about what went wrong in the process, not just the code — useful for preventing future regressions.
- "Clean slate" approach for search_queries is deliberate — no hybrid of old + new data. All rows that go through the fix get fresh data.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-fix-google-ads-data-sourcing-variant-metrics-from-shopping-performance-view-and-per-campaign-search-terms-sync*
*Context gathered: 2026-02-19*
