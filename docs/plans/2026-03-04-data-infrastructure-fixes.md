# Data Infrastructure Fix Plan

**Created:** 2026-03-04
**Source:** Deep investigation of database architecture, data flow, and dashboard integration
**Priority:** Variant snapshot bug first, then remaining tasks in order

---

## Task 1: CRITICAL — Variant Snapshot Dual-Write Not Executing

**Priority:** P0 — Blocks all variant-level performance tracking
**Status:** Root cause under investigation

### Symptoms
- `performance_snapshots_variant` has 0 rows despite daily collection running successfully
- `performance_snapshots` (master-level) got 622 rows written at 2026-03-04 07:45 UTC
- Both writes happen in the SAME function: `collect_daily_performance_snapshots()` in `src/feedops/monitoring/performance_impact.py`
- The variant write (lines 369-421) executes BEFORE the master aggregation (lines 423-521)

### Evidence Collected
1. Master snapshots for Mar 3: 622 SKUs, 11,679 total impressions — data IS flowing from Google Ads
2. Variant snapshots: 0 rows, NULL last_fetched — NOTHING was written
3. The function `fetch_batch_product_performance()` returns per-offer-ID data that feeds BOTH writes
4. The variant write skips zero-impression rows (line 377) but 11,679 impressions across variants means some MUST be non-zero
5. The upsert target table `performance_snapshots_variant` has correct unique constraint: `(gmc_offer_id, platform, environment, snapshot_date)`

### Hypotheses to Test (in order)
1. **Cloud Run is running old code** — PR #60 added the variant dual-write, but the deployed revision may predate this merge. Check: `gcloud builds list` and `gcloud run services describe` to see which revision is serving traffic
2. **GAQL query case sensitivity** — Input offer IDs are lowercase (`shopify_us_`), Google Ads stores uppercase (`shopify_US_`). The WHERE clause `segments.product_item_id IN (lowercase)` may return 0 rows. BUT: master aggregation uses the same data, so if master has data, this isn't the issue
3. **Silent upsert failure** — The Supabase upsert (line 412) doesn't log the response. A schema mismatch or constraint violation could fail silently
4. **offer_to_sku mapping empty** — If `_fetch_variant_rows_for_skus` returns rows without `gmc_offer_id`, the mapping is empty and all variant writes skip at line 382-383

### Key Files
- `src/feedops/monitoring/performance_impact.py` — Lines 369-421 (variant write), lines 256-534 (full function)
- `src/feedops/integrations/google_ads_performance.py` — Lines 303-341 (`_fetch_chunk_data`), 344-472 (`fetch_batch_product_performance`)
- `src/feedops/api/performance_baseline.py` — Lines 301-320 (endpoint that calls collection)
- `src/feedops/utils/offer_id.py` — `normalize_offer_id()` function

### Debugging Steps
1. Check Cloud Build status: `gcloud builds list --project=bobbys-project-346400 --limit=5`
2. Check serving revision: `gcloud run services describe feedops-pipeline --project=bobbys-project-346400 --region=us-east1 --format="value(status.traffic)"`
3. Check Cloud Run logs for the variant write log line: `"Wrote %d variant snapshot rows"` (line 416-419)
4. If code IS deployed, add diagnostic logging before the variant loop to log `len(by_offer)`, count of non-zero impression offers, and `len(offer_to_sku)`
5. Test the upsert independently with a single known-good row

### Resolution
Fix depends on root cause found above. If deployment issue, redeploy. If code bug, fix the specific line identified.

---

## Task 2: CRITICAL — Dashboard Performance API All-or-Nothing Variant Fallback

**Priority:** P0 — Performance page shows wrong baselines for most SKUs
**Status:** Root cause identified, fix needed

### Root Cause
`dashboard/src/app/api/performance/route.ts` lines 159-198: The fallback is binary. If ANY variant baselines exist (even for just 4 SKUs), it uses variant data for ALL SKUs.

```typescript
// Line 171 — the bug
if (varBaselines && varBaselines.length > 0) {
  usedVariantBaselines = true  // Switches ALL SKUs to variant mode
}
```

### Impact
- Only **4 SKUs** (SQ-20, CL-55, HTL-3, TS-28) have real variant baseline data
- **151 SKUs** have variant baseline rows but ALL ZEROS (97.3% zero-impression) → baseline shows 0
- **85 SKUs** have master baselines (e.g., WP-2TB/16-GAL at 990 daily impressions) but NO variant baseline rows → fall through to `{avgCtr: 0, avgImpressions: 0}`
- Net effect: Performance page shows zero baselines for almost every published SKU

### Evidence
Query comparing master vs variant baselines for top 25 SKUs by traffic:

| SKU | Master Impressions | Variant Sum | Variant Rows | Nonzero Variants |
|-----|-------------------|-------------|--------------|-----------------|
| WP-2TB/16-GAL | 990 | 0 | 0 | 0 |
| TD-23 | 936 | 0 | 28 | 0 |
| SQ-20 | 733 | **733** | 28 | **28** |
| CL-55 | 731 | **731** | 28 | **28** |
| CL-24C | 577 | 0 | 28 | 0 |
| MD-22 | 511 | 0 | 28 | 0 |

Same pattern for snapshots (lines 244-298) — same all-or-nothing logic.

### Fix
Change to per-SKU hybrid fallback:
1. Query BOTH variant and master baselines
2. For each SKU: if variant sum > 0, use variant aggregation; else use master baseline
3. Apply same pattern for snapshots
4. File: `dashboard/src/app/api/performance/route.ts`

---

## Task 3: HIGH — Legacy Snapshot Data Contamination

**Priority:** P1 — Pollutes performance calculations
**Status:** Root cause identified

### Root Cause
Old collection code (pre-v1.1) wrote Google Ads impression data to ALL platforms (google, shopify, bing) instead of just google.

### Evidence
```sql
SELECT platform, COUNT(*), MIN(snapshot_date), MAX(snapshot_date)
FROM performance_snapshots GROUP BY platform;
-- google: 1,978 rows (2025-12-31 → 2026-03-03) ← correct
-- shopify:    20 rows (2026-02-18 → 2026-02-20) ← bogus
-- bing:        3 rows (2026-02-18 → 2026-02-20) ← bogus
```

920D-6 example: Feb 18 has id=85 (shopify, 199 impr) and id=86 (google, 199 impr) — identical Google Ads data written to both platforms.

Additionally, Feb 18-20 data shows dramatically different magnitudes vs Mar 1-3:
- Feb 20: 38 SKUs, 155K total impressions (avg ~4,079/SKU) — appears cumulative
- Mar 1: 622 SKUs, 15K total impressions (avg ~24/SKU) — daily values

### Fix
```sql
-- Delete bogus shopify/bing snapshot rows
DELETE FROM performance_snapshots
WHERE platform IN ('shopify', 'bing')
AND snapshot_date BETWEEN '2026-02-18' AND '2026-02-20';
-- Should delete 23 rows

-- Evaluate Feb 18-20 google rows — if cumulative, either delete or divide by 30
-- Check: do these have fetched_at from old code?
SELECT DISTINCT fetched_at FROM performance_snapshots
WHERE snapshot_date BETWEEN '2026-02-18' AND '2026-02-20' AND platform = 'google';
```

---

## Task 4: MEDIUM — Orphaned Search Query Rows

**Priority:** P2 — Data quality cleanup
**Status:** Root cause identified

### Root Cause
441 rows in `search_queries` have garbage offer IDs (`ibqwgnex...` prefix: 213 rows, `lkeawlmn...`: 53 rows) that can't join to `variant_index`.

### Evidence
```sql
SELECT DISTINCT LEFT(gmc_offer_id, 30), COUNT(*)
FROM search_queries
WHERE gmc_offer_id NOT LIKE 'shopify_US_%' AND gmc_offer_id NOT LIKE 'shopify_us_%'
GROUP BY 1;
-- ibqwgnex: 213
-- lkeawlmn: 53
```

These are likely test data or corrupted rows from early development.

### Fix
```sql
DELETE FROM search_queries
WHERE gmc_offer_id NOT LIKE 'shopify_US_%'
AND gmc_offer_id NOT LIKE 'shopify_us_%';
-- Should delete 441 rows (266 garbage + 175 other non-standard)
```

---

## Task 5: MEDIUM — Variant Baseline Coverage Gap

**Priority:** P2 — Only 155/2,784 SKUs have variant baselines
**Status:** Understood, needs extended backfill

### Root Cause
The variant baseline backfill only ran for 155 SKUs. The existing backfill script (`scripts/backfill-performance-baselines.py`) only writes to `performance_baselines` (master table), not `performance_baselines_variant`.

### Evidence
- `performance_baselines`: 240 distinct SKUs, 332 rows
- `performance_baselines_variant`: 155 distinct SKUs, 4,079 rows
- 85 SKUs have master baselines but NO variant baselines (including high-traffic like WP-2TB/16-GAL at 990/day)
- 2,629 SKUs in variant_index have NO variant baselines at all
- Of the 4,079 variant baseline rows, 3,967 (97.3%) have zero impressions — expected for low-traffic finishes

### Fix
1. Once Task 1 is resolved (variant snapshots flowing), variant baselines can be computed from accumulated snapshot data
2. Alternatively, create a variant baseline backfill that queries Google Ads per-offer-ID for 30-day windows
3. The daily collector already writes variant snapshots (once deployed) — after 30 days, baselines can be computed from that data

---

## Task 6: LOW — Missing FK Constraints on Variant Performance Tables

**Priority:** P3 — Schema hardening
**Status:** Documented, no orphans currently

### Root Cause
`performance_baselines_variant` and `performance_snapshots_variant` have no FK constraints referencing `variant_index.gmc_offer_id`. They were created in a migration that intentionally deferred FKs.

### Evidence
- Orphan check shows 0 orphaned rows (good)
- Recommended in `docs/architecture/entity-relationships.md` lines 519-525
- Adding FKs would prevent future orphans if offer IDs are deleted from variant_index

### Fix
```sql
-- Verify no orphans first
SELECT COUNT(*) FROM performance_baselines_variant pbv
LEFT JOIN variant_index vi ON vi.gmc_offer_id = pbv.gmc_offer_id
WHERE vi.gmc_offer_id IS NULL;

-- If 0, add FKs
ALTER TABLE performance_baselines_variant
ADD CONSTRAINT fk_baselines_variant_offer_id
FOREIGN KEY (gmc_offer_id) REFERENCES variant_index(gmc_offer_id);

ALTER TABLE performance_snapshots_variant
ADD CONSTRAINT fk_snapshots_variant_offer_id
FOREIGN KEY (gmc_offer_id) REFERENCES variant_index(gmc_offer_id);
```

---

## Task 7: LOW — Reconcile sku_approvals Table

**Priority:** P3 — Data model clarity
**Status:** Observed discrepancy

### Root Cause
`sku_approvals` table has only 4 rows with `approval_status = 'approved'`, but `generated_content` has 260 Google rows with `approved_content IS NOT NULL`. Approvals are tracked in `generated_content.approved_content` column, not in the dedicated `sku_approvals` table.

### Evidence
```sql
SELECT 'sku_approvals_approved' as source, COUNT(DISTINCT master_sku) FROM sku_approvals WHERE approval_status = 'approved';
-- 4 SKUs

SELECT 'generated_content_approved' as source, COUNT(DISTINCT master_sku) FROM generated_content WHERE approved_content IS NOT NULL AND platform = 'google';
-- ~130 SKUs (260 rows across platforms)
```

### Fix
Either:
1. Backfill `sku_approvals` from `generated_content.approved_content` to keep tables in sync
2. Or deprecate `sku_approvals` and use `generated_content.approved_content IS NOT NULL` as the source of truth
3. Document which is authoritative in SCHEMA.md

---

## Execution Order

1. **Task 1** — Debug and fix variant snapshot dual-write (P0, blocks everything)
2. **Task 2** — Fix dashboard fallback logic (P0, can be done in parallel)
3. **Task 3** — Clean up legacy snapshot contamination (P1, SQL cleanup)
4. **Task 4** — Delete orphaned search query rows (P2, SQL cleanup)
5. **Task 5** — Plan variant baseline coverage extension (P2, depends on Task 1)
6. **Task 6** — Add FK constraints (P3, migration)
7. **Task 7** — Reconcile sku_approvals (P3, data model decision)
