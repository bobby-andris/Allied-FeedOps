---
phase: 11-performance-page-enhancements
verified: 2026-02-19T14:30:00Z
status: human_needed
score: 11/12 must-haves verified
human_verification:
  - test: "Navigate to /performance in the live dashboard and confirm delta values are non-zero and plausible for at least 5 published SKUs"
    expected: "Impressions and clicks show reasonable daily-average deltas (e.g. -15% to +25%), not zeros or +2500%. CTR shows non-zero baseline and current values."
    why_human: "Plan 03 fixed the baseline divisor and snapshot window filter programmatically, then verified via Supabase spot-check — but no second browser UAT was conducted after the fix was deployed. The original UAT (plan 02) found 4 major issues that were then fixed in plan 03. A human must confirm the fixes render correctly in the live dashboard."
  - test: "Click a SKU row and confirm the inline detail panel shows variant breakdown with finish names and non-zero impressions/clicks"
    expected: "Panel opens with two columns — left shows per-finish variant table with impressions/clicks/CTR, right shows top search terms. At least one variant has impressions > 0."
    why_human: "The gap closure (plan 03) changed the query from .eq('master_sku', sku) to .in('gmc_offer_id', upperOfferIds) via variant_index join. This was verified via grep but not confirmed in a live browser session after deployment."
  - test: "Change the Snapshot window selector from 30d to 7d and confirm the table updates — at least the days-since-publish column or the data refreshes"
    expected: "Changing either time selector triggers a new API fetch and the table re-renders. No stale data visible."
    why_human: "Selector wiring was confirmed via code review (useCallback dependency array includes baselineWindow and snapshotWindow), but the actual UI interaction after deployment has not been re-verified since plan 02 UAT."
---

# Phase 11: Performance Page Enhancements — Verification Report

**Phase Goal:** Users can clearly see how published SKUs are performing relative to their pre-publish baseline, with trend direction at a glance

**Verified:** 2026-02-19T14:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification
**Score:** 11/12 must-haves verified

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User sees dual time selectors: Baseline (7d/30d/60d) and Snapshot (7d/30d/60d) | VERIFIED | page.tsx lines 609-636: two `<Select>` components labeled "Baseline" and "Snapshot", each with 7d/30d/60d options, bound to `baselineWindow` and `snapshotWindow` state |
| 2 | Each row shows baseline metric values, current snapshot values, and a delta (% change) per metric | VERIFIED | `DeltaCell` component (page.tsx line 94-151) renders baseline value, current value, and colored delta%. Used for CTR, Impressions, Clicks, and CVR columns |
| 3 | Each row shows days-since-publish and published date | VERIFIED | page.tsx lines 416-419: renders `{sku.publishedAt}` and `{sku.daysSincePublish}d ago`; route.ts populates `daysSincePublish` from snapshot record or computed from publish date |
| 4 | Rows show trend icon (green up / red down / gray neutral) based on impressions delta; neutral threshold is ±3% | VERIFIED | `TrendIcon` component (page.tsx lines 164-168): `TrendingUp` if impressionsDelta >= 3, `TrendingDown` if <= -3, `Minus` otherwise. Applied per row at line 458 |
| 5 | User can toggle between "With snapshot" and "All SKUs" filter views | VERIFIED | Filter toggle (page.tsx lines 646-667); `PerformanceTable` applies `filterMode === 'published' ? skus.filter(s => s.hasSnapshot) : skus` at line 336-338 |
| 6 | Clicking a sortable column header sorts the table by that metric's delta | VERIFIED | `SortableHeader` at module scope (page.tsx lines 233-255); `handleSort` toggles `sortDir` or changes `sortColumn`; `PerformanceTable` sorts by `computeDelta` for metric columns and by `daysSincePublish` for days column |
| 7 | SKUs with no snapshot show "No snapshot" badge instead of delta values | VERIFIED | `DeltaCell` (lines 105-115): when `hasSnapshot=false`, renders baseline value + `<Badge variant="outline">No snapshot</Badge>`; rows get `bg-muted/30` background |
| 8 | Clicking a SKU row expands inline detail panel showing per-variant breakdown and top search terms | VERIFIED | `handleRowClick` (page.tsx lines 538-554) fetches `?sku=X&snapshotWindow=Y&baselineWindow=Z`; `ExpandedSkuDetail` component (lines 257-312) renders as `<TableRow colSpan={8}>` inline. `expandedSku` state controls single-row-at-a-time expansion |
| 9 | Baseline impressions/clicks are daily averages (total / days_lookback, not total / variant_count) | VERIFIED | performance_baseline.py lines 285-289: `days_lookback = (...).days; avg_impressions = total_impressions / days_lookback; avg_clicks = total_clicks / days_lookback`. Comment confirms intent. |
| 10 | Snapshot selection uses most recent snapshot (no date-ceiling filter that would exclude backfilled data) | VERIFIED | route.ts lines 237-238: `const windowSnapshot = snapshots.length > 0 ? snapshots[0] : undefined`. No `.find()` with date ceiling. Sorted DESC so index 0 is most recent. |
| 11 | SKU detail panel queries search_queries via variant_index offer-ID join (resilient to null master_sku in historical rows) | VERIFIED | route.ts lines 331-359: fetches `variant_index` for gmc_offer_ids, constructs `upperOfferIds`, then `.in('gmc_offer_id', upperOfferIds)`. The old `.eq('master_sku', sku)` is replaced. |
| 12 | Real data confirmed in live dashboard showing non-zero accurate deltas for published SKUs (VER-01) | UNCERTAIN | Initial UAT (plan 02) confirmed 5/9 tests pass including trend icons, sort, expand/collapse. The 4 major issues were fixed in plan 03 (baseline divisor, snapshot window, SKU detail query, lowercase fix). Plan 03 verified fixes via Supabase spot-checks and grep, but no post-fix browser session was documented. Needs human confirmation. |

**Score:** 11/12 truths verified (1 uncertain, needs human)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `dashboard/src/app/api/performance/route.ts` | Enhanced GET endpoint returning daysSincePublish, baselineWindow, snapshotWindow, variant-keyed snapshots | VERIFIED | 490 lines. Exports `GET`. Contains `SkuPerformance` interface with `daysSincePublish`, `hasSnapshot`, `baselineWindow`, `snapshotWindow`. Contains `SkuDetail`, `VariantPerformance`, `SearchTerm` interfaces. No Google Ads live call imports. |
| `dashboard/src/app/(dashboard)/performance/page.tsx` | Rewritten performance page with dual time selectors, delta table, filter toggle, sort, trend indicators (min 300 lines) | VERIFIED | 819 lines — well above 300 and 400 line minimums. `"use client"` directive. Contains `DeltaCell`, `SortableHeader`, `TrendIcon`, `LoadingSkeleton`, `ChangeCard`, `ExpandedSkuDetail`, `PerformanceTable`, `PerformancePage` components. |
| `src/feedops/api/performance_baseline.py` | Corrected baseline divisor: total_impressions / days_lookback | VERIFIED | Lines 285-289: `days_lookback = (...).days; avg_impressions = total_impressions / days_lookback if days_lookback > 0 else 0.0; avg_clicks = total_clicks / days_lookback if days_lookback > 0 else 0.0` |
| `src/feedops/integrations/google_ads_search_terms.py` | Lowercase gmc_offer_id before variant_index lookup | VERIFIED | Line 382: `gmc_offer_id = gmc_offer_id.lower()` at top of `get_variant_info()` before cache key and DB query |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `page.tsx PerformancePage` | `/api/performance` | `fetch` with `baselineWindow` and `snapshotWindow` params | WIRED | Lines 507-508: `const url = \`/api/performance?baselineWindow=${baselineWindow}&snapshotWindow=${snapshotWindow}${platformParam}\`` called in `fetchData` useCallback |
| `page.tsx PerformanceTable` | `SkuPerformance.daysSincePublish` | days-since-publish column rendered per row | WIRED | Line 418: `<div className="text-xs text-muted-foreground">{sku.daysSincePublish}d ago</div>` |
| `page.tsx ExpandedSkuDetail` | `/api/performance?sku=X&snapshotWindow=Y&baselineWindow=Z` | fetch on expandedSku change in handleRowClick | WIRED | Lines 547-549: `fetch(\`/api/performance?sku=${encodeURIComponent(masterSku)}&snapshotWindow=${snapshotWindow}&baselineWindow=${baselineWindow}\`)` |
| `ExpandedSkuDetail` | `search_queries table` via `topSearchTerms[]` | route.ts returns topSearchTerms in skuDetail | WIRED | route.ts lines 433-460: builds `termMap`, deduplicates, sorts, returns top 10. page.tsx lines 298-308: renders `detail.topSearchTerms.map(...)` |
| `performance_baseline.py` | `performance_baselines` table | upsert with corrected avg_impressions / avg_clicks using days_lookback | WIRED | Lines 299-317: `baseline_data` dict includes `avg_impressions` and `avg_clicks` computed via `days_lookback`; passed to `.upsert()` |
| `route.ts` | `performance_snapshots` | `snapshots[0]` (most recent, no date ceiling) | WIRED | Lines 237-238: `const windowSnapshot = snapshots.length > 0 ? snapshots[0] : undefined` |
| `route.ts` | `search_queries` via `variant_index` | `.in('gmc_offer_id', upperOfferIds)` after fetching from variant_index | WIRED | Lines 331-359: variant_index query → offerIds → upperOfferIds → `.in('gmc_offer_id', upperOfferIds)` |

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PERF-01 | 11-01, 11-02, 11-03 | Performance page shows clear before/after comparison (baseline vs. latest snapshot) per published SKU | SATISFIED | `DeltaCell` renders baseline → current → delta% for CTR, Impressions, Clicks, CVR per row. API returns `baseline` and `current` objects per SKU with correct normalization (daily averages). |
| PERF-02 | 11-01, 11-02, 11-03 | User can see days-since-publish alongside metric deltas | SATISFIED | `daysSincePublish` field in API response, rendered as `{N}d ago` per row in the Published column. |
| PERF-03 | 11-01, 11-02, 11-03 | Page visually surfaces which SKUs are trending up vs. down since publish | SATISFIED | `TrendIcon` component renders per row: `TrendingUp` (green), `TrendingDown` (red), or `Minus` (gray) based on impressions delta with ±3% neutral threshold. |
| VER-01 | 11-02, 11-03 | All UI changes visually inspected using browser automation before marked complete | PARTIAL | Initial UAT via agent-browser confirmed 5/9 tests. 4 gaps were diagnosed and fixed in plan 03. No post-fix browser session documented. Code changes verified via grep/build checks. Human re-verification needed. |

**Orphaned requirements check:** REQUIREMENTS.md maps PERF-01, PERF-02, PERF-03, and VER-01 to Phase 11. All four are claimed in at least one plan's `requirements` field. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | — |

**Anti-pattern scan results:**
- No TODO/FIXME/PLACEHOLDER comments in the modified files
- No empty implementations (`return null`, `return {}`, `return []`)
- No stub API handlers (all routes return real database-queried data)
- No console.log-only implementations
- Live Google Ads imports (`fetchShoppingPerformance`, `isGoogleAdsConfigured`, `getDateRange`) are confirmed absent from route.ts

---

## Build Verification

| Check | Result | Details |
|-------|--------|---------|
| `npm run build` | PASS | Zero TypeScript errors. `/performance` page compiled as static. |
| `npm run lint` | PASS | Zero errors. 2 pre-existing warnings in unrelated files (`backfill-health/route.ts`, `ReviewListClient.tsx`) — both present before Phase 11 and not caused by this phase. |

---

## Human Verification Required

### 1. Delta values are non-zero and plausible after gap closure

**Test:** Navigate to https://allied-feed-ops.vercel.app/performance. Review the delta table.
**Expected:** At least 5 published SKU rows show non-zero impressions/clicks deltas (e.g., -15% or +12%), not zeros or +2500%. Summary cards show non-zero "Avg CTR Change" or "Avg CVR Change". Info banner reads "daily averages".
**Why human:** Plan 03 fixed the baseline divisor (Python) and snapshot window filter (TypeScript) programmatically. Verified via Supabase spot-check showing daily-average values (e.g., 60.47 impr/day for SKU 1016). No browser session confirmed the live page reflects these fixes after deployment.

### 2. Inline variant detail panel shows data for at least one SKU

**Test:** Click any SKU row in the performance table. Inspect the expanded panel.
**Expected:** Left column shows a table with at least one row of variant data (finish name + impressions > 0). Right column shows at least one search term.
**Why human:** Plan 03 changed the SKU detail query from `.eq('master_sku', sku)` to `.in('gmc_offer_id', upperOfferIds)` via variant_index join. Confirmed via grep that the new query is in place, but no live dashboard verification was done post-deployment to confirm real variant data populates the panel.

### 3. Changing time selectors refreshes the table

**Test:** On the performance page, change the "Snapshot" selector from "30 days" to "7 days".
**Expected:** A loading state briefly appears and the table updates (data may or may not change depending on available snapshots, but a new API call must fire).
**Why human:** `useCallback` dependency array is verified to include `snapshotWindow` (line 523), so re-fetch is wired in code. Live confirmation that selector changes trigger a visible refresh has not been re-documented since plan 02 UAT.

---

## Gaps Summary

No blocking code gaps identified. All 11 programmatically-verifiable must-haves pass at all three levels (exists, substantive, wired). The one uncertain truth (VER-01 / truth #12) is inherently a human concern — it asks whether real data appears correctly in the live browser, which cannot be determined from code inspection alone.

The gap closure work in plan 03 is verified in the codebase:
- `performance_baseline.py` uses `days_lookback` as divisor (not `variants_with_data`)
- `route.ts` uses `snapshots[0]` (not a date-ceiling `.find()`)
- `route.ts` SKU detail uses `variant_index` join + `.in('gmc_offer_id', upperOfferIds)`
- `google_ads_search_terms.py` lowercases `gmc_offer_id` at `get_variant_info()` entry

The 37 published SKUs' baselines were re-captured after the Python fix deployed, per the plan 03 summary (spot-checked values: 1016: 60.47 impr/day, 1051: 224 impr/day). These values are stored in Supabase, not in the code, so they cannot be re-verified programmatically.

---

_Verified: 2026-02-19T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
