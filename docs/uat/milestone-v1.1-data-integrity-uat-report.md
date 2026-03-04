# Milestone v1.1 — Data Integrity UAT Report

**Date:** 2026-03-04
**Tester:** Claude Opus 4.6 (automated)
**SKUs Tested:** FT-16, 7272D/30, DT-HTL/24-5
**Verdict: FAIL — 4 blocking issues, milestone not ready for sign-off**

---

## Executive Summary

Milestone v1.1 delivered real pipeline infrastructure work (offer ID normalization in Python, variant table schemas, dead code cleanup, image wiring, test cleanup). However, the data infrastructure goals are **incomplete**:

- Variant-level performance tables exist but have **0 rows** — deployed code was never triggered
- The dashboard queries everything by `master_sku` strings — no dashboard code was updated to use proper `gmc_offer_id` joins
- 23.6% of SKUs (657 out of 2,784) cannot be navigated to via URL due to slash handling
- Performance page shows impressions/clicks that are **~30x too low** due to a normalization bug

The Phase 8.1 Python code (offer ID utility, dual-write logic, backfill script) is deployed and correct. The gap is: it was never activated, and the dashboard never adopted the new data model.

---

## Blocking Issues

### BLOCKER #1: Variant Performance Tables Empty (0 Rows)

**Tables:** `performance_snapshots_variant`, `performance_baselines_variant`
**Status:** Tables exist (migration 043 applied), but contain 0 rows.

**Root cause:** The dual-write code in `performance_impact.py` only executes when `/performance/collect-daily` is called on Cloud Run. This endpoint was never triggered after deployment. The bulk baseline backfill script (`scripts/bulk_baseline_backfill.py`) was never run.

**Impact:** The entire variant-level performance tracking system is dark. No variant-level baselines, no variant-level snapshots, no variant-level impact scores. All performance data remains aggregated at `master_sku` level only.

**To fix:**
1. Run the 50-SKU test gate: `GOOGLE_ADS_API_ENABLED=1 PYTHONPATH=./src python scripts/bulk_baseline_backfill.py --test-gate`
2. If match rate >=90%, run full backfill: `python scripts/bulk_baseline_backfill.py`
3. Trigger daily collection: `curl -X POST "$FEEDOPS_PIPELINE_URL/performance/collect-daily"`
4. Set up Cloud Scheduler to call `/performance/collect-daily` daily at 6:00 AM UTC

### BLOCKER #2: Dashboard Queries Use `master_sku` Instead of `gmc_offer_id`

**Affected pages:** Performance, Content Impact, Review (performance card), Search Insights
**Files:** `dashboard/src/app/api/performance/route.ts`, review page `page.tsx`, content-impact `page.tsx`

**Root cause:** Phase 8.1 created the entity relationship documentation (ENTM-03) recommending `gmc_offer_id` as the proper join key for Google Ads data. But zero dashboard TypeScript files were modified. Every dashboard query still joins on `master_sku` strings.

**Impact:**
- Google Ads data is variant-level (per offer ID), but the dashboard treats it as master-level
- Multi-SKU products (e.g., DMF-2/2X through 2/5X sharing one `shopify_product_id`) have no way to distinguish variant performance
- No variant-level performance breakdown exists in the dashboard despite variant data being available in `search_queries.gmc_offer_id`

**To fix:** Update dashboard API routes to join on `gmc_offer_id` via `variant_index`, distinguish variant-level vs master-level metrics, and surface variant performance alongside master aggregates.

### BLOCKER #3: Performance Page Snapshot Normalization Bug

**File:** `dashboard/src/app/api/performance/route.ts:265`
**Code:** `impressions: Math.round((windowSnapshot!.impressions || 0) / snapshotWindowDays)`

**Root cause:** The code divides snapshot impressions by `snapshotWindowDays` (default 30) assuming snapshots contain cumulative data over the window. But each snapshot row is a **single day's** data. Dividing one day by 30 produces values ~30x too low.

**Example:** FT-16 latest snapshot: 260 daily impressions → Performance page shows `Math.round(260/30) = 9` → displays -97.1% change vs baseline 311.9. The review page correctly shows 19.9K (30-day aggregate).

**Impact:** Every "current" impression and click value on the Performance page is wrong. Users would conclude every optimization is failing catastrophically. This page is unusable for evaluating content ROI.

**To fix:** Remove the `/ snapshotWindowDays` division, or correctly aggregate all snapshots within the window before computing the daily average.

### BLOCKER #4: URL Routing Broken for 23.6% of SKUs

**File:** `dashboard/src/app/(dashboard)/review/[sku]/page.tsx:71-101`
**Affected:** 657 out of 2,784 master SKUs (23.6%) — every SKU containing a `/` character

**Root cause:** `getSkuCandidates()` regex assumes slashes only replace digit-boundary hyphens (e.g., `WP-2/16-GAL`). SKUs where the slash follows a letter segment (e.g., `DT-HTL/24-5`, `BL-GTL/72-5`, `SB-DT/48-5`) are not matched. The regex converts `DT-HTL-24-5` → `DT-HTL-24/5` instead of the correct `DT-HTL/24-5`.

**Example:** `/review/DT-HTL-24-5` returns 404. Only `/review/DT-HTL%2F24-5` works.

**Impact:** Nearly a quarter of the product catalog cannot be navigated to from external links, bookmarks, or any URL constructed from the master_sku name. Users must know to URL-encode the slash manually.

**To fix:** Either add a letter-to-digit boundary regex pattern, or better: stop using `master_sku` strings in URLs entirely and use a numeric database ID instead.

---

## What Phase 8.1 Actually Delivered (Code Exists, Deployed, Correct)

| Deliverable | Status | File |
|------------|--------|------|
| Offer ID normalization utility | Deployed, working | `src/feedops/utils/offer_id.py` (53 lines) |
| Normalization applied to 4 Python codepaths | Deployed, working | `google_ads_performance.py`, `google_ads_search_terms.py`, `performance_impact.py`, `performance_baseline.py` |
| Variant performance table schemas | Applied to DB | `supabase/migrations/043_variant_performance_tables.sql` |
| Variant dual-write logic | Deployed, never triggered | `src/feedops/monitoring/performance_impact.py:370-416` |
| Bulk baseline backfill script | Exists, never run | `scripts/bulk_baseline_backfill.py` (661 lines) |
| Entity relationship documentation | Complete | `docs/architecture/entity-relationships.md` (585 lines) |

## What Was NOT Done

| Gap | Why it matters |
|-----|---------------|
| Backfill script never run | 0 rows in variant baseline table; no variant-level pre-optimization metrics |
| Daily collection never triggered | 0 rows in variant snapshot table; no variant-level post-publish tracking |
| Impact scores never computed | `performance_impact_scores` likely empty or stale |
| Dashboard not updated to use `gmc_offer_id` | All pages still query by `master_sku`; entity relationship patterns documented but not adopted |
| Performance page normalization not fixed | Existed before Phase 8.1; Phase 8.1 didn't touch dashboard code |
| URL routing not fixed | Uses `master_sku` strings; 23.6% of catalog unreachable |
| Cloud Scheduler not set up | No automated daily snapshot collection |

---

## Non-Blocking Findings (Verified Correct)

| Test Area | Result | Notes |
|-----------|--------|-------|
| Performance Baselines (review page) | PASS | FT-16: 311.9/4.1/1.31%/$40.25 matches DB exactly |
| Performance Snapshots 30d (review page) | PASS | FT-16: 19.9K impressions matches DB sum of 19,862 |
| Quality Scores | PASS | FT-16: 91% matches DB 91.67; others computed client-side from sub-scores |
| Search Insights page | PASS | Correct data from `search_queries` table, properly aggregated |
| Content Impact page | PASS | Baseline CTR, windowed CTR, deltas all internally consistent |
| Publish events | PASS | FT-16: Feb 8 publish correctly recorded; 7272D/30: 11 events |
| Variant counts | PASS | FT-16=28, 7272D/30=25, DT-HTL/24-5=28 all match DB |

These are surface-level correct but built on the wrong foundation (`master_sku` joins instead of `gmc_offer_id`).

---

## Ground Truth Data (for next session's verification)

### FT-16 (Google)
- **Baseline:** avg_impressions=311.9, avg_clicks=4.1, avg_ctr=0.0131, avg_conversion_value=$40.25, period 2026-01-20 → 2026-02-19
- **Snapshots (30d):** 5 rows, total 19,862 impressions, 250 clicks, $1,542.50 revenue
- **Latest snapshot:** Mar 3: 260 impr, 1 click, 0.38% CTR, 23 days since publish
- **Quality:** 91.67 (all platforms)
- **Top search query:** "unlacquered brass towel ring" — 1,474 impressions (single variant row)
- **Variants:** 28
- **Published:** Feb 8, 2026 (Google + Shopify)

### 7272D/30 (Google)
- **Baseline:** none
- **Snapshots:** 3 rows, all zeros (0 impressions)
- **Quality:** null in DB, 69% computed client-side
- **Search queries:** none
- **Variants:** 25
- **Published:** 11 events, Mar 3-4, 2026

### DT-HTL/24-5 (Google)
- **Baseline:** avg_impressions=6.6, avg_clicks=0.03, avg_ctr=0.0051
- **Snapshots:** none
- **Quality:** null in DB, 80% computed client-side
- **Search queries:** none
- **Variants:** 28
- **Published:** none
- **URL bug:** `/review/DT-HTL-24-5` → 404; `/review/DT-HTL%2F24-5` → works

---

## Recommendation

Do NOT create a new milestone. The Phase 8.1 infrastructure code is deployed and correct. What's needed is:

1. **Activate the deployed code** — run backfill, trigger daily collection, set up Cloud Scheduler
2. **Fix the Performance page bug** — remove or correct the `/ snapshotWindowDays` division
3. **Update dashboard queries** — adopt `gmc_offer_id` joins per the entity relationship doc
4. **Fix URL routing** — either improve `getSkuCandidates` regex or switch to numeric IDs

This is completion of existing work, not new development.
