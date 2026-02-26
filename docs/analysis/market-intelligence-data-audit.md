# Market Intelligence Data Consistency Audit

**Date**: 2026-02-26
**Auditor**: Claude Opus 4.6
**Scope**: Ground truth DB numbers vs API route logic

---

## Environment

- **Materialized View**: `market_intelligence_mv`
- **Total rows in MV**: 15,058
- **Periods**: 11 (ranging from 2025-08-23 to 2026-01-29)
- **Unique terms across all periods**: 5,962
- **Latest "major" period** (>500 terms): `2026-01-20` (3,685 unique terms)
- **Prior major period**: `2026-01-16` (767 terms, row_count = unique_terms, MV is already deduped)

---

## 1. DEMAND TAB — Period: 2026-01-20

**API route**: `/api/market-intelligence/demand`
**Data source**: `market_intelligence_term_metrics` RPC with `p_period_start = '2026-01-20'`

### 1a. Core Metrics (Ground Truth)

| Metric | Value |
|--------|-------|
| Total terms | **3,685** |
| Total impressions | **331,359** |
| Total clicks | **2,597** |
| Total spend | **$5,405.59** |
| Total conversions | **75.78** |
| Total revenue | **$15,629.16** |
| Avg CPC (where clicks > 0) | **$2.00** |

**RPC verification**: `market_intelligence_term_metrics(null, '2026-01-20')` returns **3,685 rows** -- MATCHES.

### 1b. New Term Discovery

| Comparison Method | New Terms |
|---|---|
| Latest (2026-01-20) vs ALL prior periods | 1,351 |
| Latest (2026-01-20) vs prior major period (2026-01-16) only | **2,920** |

**API behavior**: `fetchPriorPeriod()` finds `2026-01-16` (767 rows, passes `>500` check). API compares ONLY against that single prior period, NOT all prior periods. **Expected API result: 2,920 new terms.**

Note: This is a significant difference (2,920 vs 1,351). The API's single-period comparison inflates "new" terms because the prior period (767 terms) is much smaller than the latest (3,685). Terms present in older periods (2025-12-21 had 3,205) but absent from 2026-01-16 are incorrectly flagged as "new."

### 1c. Long-Tail Analysis

| Bucket | Term Count | Revenue | Spend | ROAS | Impressions | Conversions |
|--------|-----------|---------|-------|------|-------------|-------------|
| 1-2 words | 186 | $1,618.29 | $399.25 | 4.05 | 27,715 | 6.80 |
| 3-4 words | 2,238 | $9,249.65 | $3,129.71 | 2.96 | 199,185 | 40.33 |
| 5+ words | 1,261 | $4,761.22 | $1,876.63 | 2.54 | 104,459 | 28.64 |
| **TOTAL** | **3,685** | **$15,629.16** | **$5,405.59** | — | **331,359** | **75.78** |

Long-tail totals match 1a core metrics -- CONSISTENT.

---

## 2. PRODUCTS TAB — Period: 2026-01-20

**API route**: `/api/market-intelligence/products`
**Data source**: `market_intelligence_product_groups` RPC with `p_period_start = '2026-01-20'`

### 2a. Group Overview

| Metric | Direct MV Query | Product Groups RPC | Delta |
|--------|----------------|-------------------|-------|
| Group count | 60 (incl. empty label) | **59** | -1 |
| Total terms | 3,685 | **3,000** | **-685** |

**ROOT CAUSE**: The `market_intelligence_product_groups` RPC filters `WHERE custom_label_0 != ''`, excluding 685 terms with empty `custom_label_0`. This is **by design** (empty label = unmatched to a product group), but means the Products tab's `period.totalTerms` (3,000) will NOT match the Demand tab's `period.totalTerms` (3,685).

### 2b. Top Product Groups by Revenue (RPC output)

| Product Group | Terms | Revenue | ROAS | Impressions |
|---|---|---|---|---|
| (empty - excluded by RPC) | 685 | $2,813.59 | 4.23 | 34,941 |
| vanity towel rings | 74 | $1,456.24 | 7.66 | 11,224 |
| retractable hooks | 53 | $1,402.35 | 4.63 | 10,133 |
| european style tp holder | 69 | $1,083.76 | 11.10 | 8,863 |
| double glass shelf with towel bar | 182 | $1,077.33 | 3.35 | 21,009 |
| wall mounted double towel bar | 79 | $1,035.91 | 3.40 | 9,255 |
| paper towel holders | 245 | $918.35 | 2.02 | 32,021 |
| towel shelves | 116 | $893.75 | 3.68 | 12,111 |
| shower curtain brackets | 82 | $741.66 | 3.42 | 12,677 |
| double glass shelf | 86 | $635.25 | 4.66 | 5,657 |

---

## 3. COMPETITIVE TAB — ALL Periods

**API route**: `/api/market-intelligence/competitive`
**Data source**: `market_intelligence_term_metrics` RPC with `p_period_start = null` (no period filter)

### 3a. Brand Split (Ground Truth)

| Segment | Term Count | Revenue | Spend | ROAS | Impressions | Clicks | Conversions |
|---------|-----------|---------|-------|------|-------------|--------|-------------|
| brand | **27** | $4,515.13 | $565.66 | 7.98 | 21,094 | 128 | 17.35 |
| competitor | **27** | $0.00 | $9.36 | 0.00 | 805 | 5 | 0.0 |
| non_brand | **5,908** | $114,842.48 | $32,511.09 | 3.53 | 1,594,239 | 14,044 | 539.87 |
| **TOTAL** | **5,962** | **$119,357.61** | **$33,086.11** | — | **1,616,138** | **14,177** | **557.22** |

**API verification**: RPC returns 15,058 rows, JS aggregates to 5,962 unique terms. 27 + 27 + 5,908 = 5,962 -- CONSISTENT.

### 3b. Competitor Mention Breakdown (by token, all periods)

| Competitor Token | Unique Terms |
|---|---|
| kohler | 10 |
| moen | 8 |
| delta | 3 |
| grohe | 2 |
| pfister | 0 |
| american standard | 0 |
| brizo | 0 |
| rohl | 0 |
| symmons | 0 |
| jacuzzi | 0 |
| kingston brass | 0 |
| signature hardware | 0 |
| kraus | 0 |
| vigo | 0 |

Note: Some terms may match multiple tokens. Total unique competitor terms = 27 (after dedup across tokens).

### 3c. KPIs (computed from brand split)

| KPI | Expected Value |
|-----|---------------|
| brandRevenuePercent | 3.78% ($4,515.13 / $119,357.61) |
| competitorSpend | $9.36 |
| topCompetitor | "kohler" (highest spend among competitor tokens) |
| nonBrandRoas | 3.53 |

---

## 4. DISCREPANCIES & ISSUES FOUND

### Issue 1: Products tab term count mismatch (KNOWN, BY DESIGN)
- **Demand tab** reports 3,685 total terms
- **Products tab** reports ~3,000 total terms
- **Cause**: Product groups RPC excludes 685 terms with empty `custom_label_0`
- **Impact**: Users may notice different total term counts across tabs
- **Severity**: LOW (cosmetic, but could confuse users)

### Issue 2: New term detection compares only against single prior period
- **Current**: Compares 2026-01-20 (3,685 terms) vs 2026-01-16 (767 terms) = **2,920 "new" terms**
- **More accurate**: Compare vs ALL prior periods = **1,351 truly new terms**
- **Impact**: 1,569 terms are falsely flagged as "new" (they existed in older periods like 2025-12-21)
- **Severity**: MEDIUM (inflated new term count by 2.16x)
- **Root cause**: `fetchPriorPeriod()` only finds the immediately prior major period, not the full history

### Issue 3: Two RPC function overloads exist (legacy risk)
- Both `market_intelligence_term_metrics` and `market_intelligence_product_groups` have two overloads:
  - 1-arg: `(p_custom_label_0 text)` -- legacy, no period filter
  - 2-arg: `(p_custom_label_0 text, p_period_start text)` -- current, with period filter
- The 1-arg overload of `product_groups` does NOT filter by period, aggregating ALL periods
- **Impact**: If Supabase resolves to wrong overload, data would span all periods silently
- **Severity**: LOW (API code passes 2 args explicitly, but overload ambiguity is fragile)

### Issue 4: Competitive tab period.from/to are empty strings
- The API sets `period: { from: '', to: '', totalTerms: allTerms.length }` (hardcoded empty strings)
- **Impact**: UI cannot display the date range for competitive data
- **Severity**: LOW (cosmetic)

---

## 5. DATA CONSISTENCY SUMMARY

| Check | Status | Notes |
|-------|--------|-------|
| MV row count matches RPC (all periods) | PASS | 15,058 rows |
| MV unique terms matches RPC (latest period) | PASS | 3,685 terms |
| Demand tab total terms | PASS | 3,685 |
| Demand tab long-tail totals sum to correct total | PASS | 186 + 2,238 + 1,261 = 3,685 |
| Products tab group count | PASS* | 59 groups (excludes empty label by design) |
| Products tab term total vs demand tab | MISMATCH | 3,000 vs 3,685 (685 unlabeled terms excluded) |
| Competitive tab unique terms | PASS | 5,962 after JS aggregation |
| Competitive brand split sums | PASS | 27 + 27 + 5,908 = 5,962 |
| New term count accuracy | ISSUE | 2,920 reported vs 1,351 truly new (2.16x inflation) |
| Competitive period display | ISSUE | Empty strings for from/to dates |
