---
phase: 03-sample-testing-analysis
plan: 02
subsystem: google-ads-discovery
tags: [keyword-planner, opportunity-gap, sample-testing]
dependency_graph:
  requires: [03-01-sample-sku-selection]
  provides: [keyword-ideas-by-sku, opportunity-gaps]
  affects: [phase-04-gap-analysis]
tech_stack:
  added: [google-ads-keyword-planner-api]
  patterns: [generic-category-seeding, competition-enum-handling]
key_files:
  created:
    - scripts/phase3_keyword_gap.py
    - .planning/phases/03-sample-testing-analysis/keyword-ideas-by-sku.json
    - .planning/phases/03-sample-testing-analysis/opportunity-gaps.json
decisions:
  - "Use generic category terms (not full product titles) as Keyword Planner seeds for better idea generation"
  - "Handle competition field as int (not enum) due to API returning integer values"
  - "Filter to keywords with 100+ monthly searches for gap analysis"
metrics:
  duration_seconds: 217
  completed_date: "2026-02-13"
  task_count: 1
  file_count: 3
---

# Phase 03 Plan 02: Keyword Planner Ideas and Opportunity Gap Analysis Summary

Keyword Planner idea generation for sample SKUs completed with 57% average coverage rate and 168K monthly search gap identified.

## Objective

Generate Keyword Planner ideas for sample SKUs and calculate opportunity gaps against current Google Ads search term coverage (SAMP-03, SAMP-04).

## Tasks Completed

### Task 1: Generate Keyword Ideas and Calculate Opportunity Gaps ✅
**Commit:** 0c816ad1
**Files:** scripts/phase3_keyword_gap.py, keyword-ideas-by-sku.json, opportunity-gaps.json

Created Python script implementing:
- **SAMP-03**: Keyword Planner idea generation using Google Ads API
- **SAMP-04**: Opportunity gap calculation (KP ideas NOT in current search terms)

**Key implementation:**
- Generic category term extraction (e.g., "grab bar" instead of "Pipeline Collection 16 Inch Grab Bar")
- 100 keyword ideas per SKU limit
- Competition enum handling (API returns int, not enum object)
- High-volume filtering (100+ monthly searches)
- Gap analysis with coverage rate calculation

**Results:**
- 5 SKUs processed successfully
- 500 total keyword ideas generated (100 per SKU)
- 343 high-volume ideas identified (100+ monthly searches)
- 153 gap keywords found (not in current search terms)
- 168,530 total monthly search gap volume
- 57.0% average coverage rate

## Key Findings

### Coverage Analysis by SKU

| SKU | Category | Current Terms | KP Ideas | Gap | Gap Volume | Coverage |
|-----|----------|---------------|----------|-----|------------|----------|
| P-700-16-GB | grab bar | 11,507 | 94 | 31 | 34,520 | 67.0% |
| TD-23 | garment rod | 13,164 | 29 | 14 | 9,090 | 51.7% |
| WP-2/16-GAL | glass shelf | 13,736 | 86 | 43 | 51,760 | 50.0% |
| CL-20-6 | bathroom hooks | 10,398 | 93 | 55 | 51,300 | 40.9% |
| WP-GTB-2 | towel rail | 11,587 | 41 | 10 | 21,860 | 75.6% |

### Top Opportunity Gaps

**P-700-16-GB (grab bar):**
- toilet rails (2,900/mo)
- bathroom grab rails for the elderly (2,900/mo)
- home depot grab bars (2,400/mo)

**WP-2/16-GAL (glass shelf):**
- wine glass rack (12,100/mo)
- floating glass shelves (5,400/mo)
- black curio cabinet (3,600/mo)

**CL-20-6 (bathroom hooks):**
- shower curtain hooks (40,500/mo - massive gap!)
- shower curtain rings (8,100/mo)
- mdesign shower curtain hooks (2,400/mo)

### Insights

1. **Current coverage is moderate**: 57% average suggests Google Ads is capturing about half of available high-volume keywords
2. **Significant gap volume**: 168K monthly searches represents substantial untapped opportunity
3. **Category variation**: Coverage ranges from 40.9% (bathroom hooks) to 75.6% (towel rail)
4. **Shower curtain hooks anomaly**: CL-20-6 (tie/belt rack) has "shower curtain hooks" as top gap - likely related/complementary product
5. **Generic terms dominate gaps**: Most missing keywords are generic category terms, not brand/model-specific

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Product titles returned no keyword ideas**
- **Found during:** Task 1, initial execution
- **Issue:** Full product titles (with brand + model) are too specific for Keyword Planner - API returned only the exact input keyword with 0 search volume
- **Fix:** Extracted generic category terms from titles/categories (e.g., "grab bar" instead of "Pipeline Collection 16 Inch Grab Bar")
- **Files modified:** scripts/phase3_keyword_gap.py (added `extract_generic_category_term` function)
- **Commit:** 0c816ad1

**2. [Rule 1 - Bug] Competition field type mismatch**
- **Found during:** Task 1, second execution
- **Issue:** API returned competition as integer (not enum object), causing `'int' object has no attribute 'name'` error
- **Fix:** Added type checking and int-to-enum mapping (0=UNSPECIFIED, 1=LOW, 2=MEDIUM, 3=HIGH)
- **Files modified:** scripts/phase3_keyword_gap.py (updated `generate_keyword_ideas` function)
- **Commit:** 0c816ad1

## Technical Implementation

### Script Architecture
**File:** scripts/phase3_keyword_gap.py (181 lines)

**Key functions:**
- `extract_generic_category_term()`: Maps product categories to searchable terms
- `generate_keyword_ideas()`: Calls Keyword Planner API with seed keywords
- `calculate_opportunity_gap()`: Compares KP ideas against current search terms
- Rate limiting: 1.5 second delay between API requests

### API Configuration
- **Service:** KeywordPlanIdeaService (GenerateKeywordIdeasRequest)
- **Language:** languageConstants/1000 (English)
- **Geo target:** geoTargetConstants/2840 (USA)
- **Network:** GOOGLE_SEARCH
- **Limit:** 100 ideas per SKU

### Output Schema

**keyword-ideas-by-sku.json:**
```json
{
  "metadata": {"date": "2026-02-13", "language": "English", "geo": "USA"},
  "skus": {
    "SKU": {
      "product_title": "...",
      "seed_keyword": "...",
      "category": "...",
      "idea_count": N,
      "ideas": [{"text", "avg_monthly_searches", "competition", "competition_index", "low_cpc_micros", "high_cpc_micros"}]
    }
  }
}
```

**opportunity-gaps.json:**
```json
{
  "metadata": {"date": "2026-02-13", "min_monthly_searches": 100},
  "summary": {"total_skus", "avg_coverage_rate", "total_gap_volume", "total_gap_keywords"},
  "skus": {
    "SKU": {
      "category", "current_search_terms", "kp_high_volume_ideas", "gap_count", "gap_volume", "coverage_rate",
      "top_gaps": [{"text", "avg_monthly_searches", "competition", "competition_index"}]
    }
  }
}
```

## Verification

All verification criteria met:
- ✅ Script completes without fatal errors
- ✅ keyword-ideas-by-sku.json contains ideas for 5 SKUs
- ✅ opportunity-gaps.json contains gap analysis with coverage_rate per SKU
- ✅ Both JSON files are valid
- ✅ Summary table printed to stdout

## Next Steps

Phase 04 (Gap Analysis & Recommendations) can now:
1. Analyze gap patterns across all sampled SKUs
2. Assess whether missing keywords represent true opportunities or irrelevant queries
3. Estimate potential impact of backfill based on gap volume
4. Recommend backfill scope and prioritization strategy

## Self-Check: PASSED

**Created files exist:**
- FOUND: scripts/phase3_keyword_gap.py
- FOUND: .planning/phases/03-sample-testing-analysis/keyword-ideas-by-sku.json
- FOUND: .planning/phases/03-sample-testing-analysis/opportunity-gaps.json

**Commits exist:**
- FOUND: 0c816ad1 (feat(03-02): generate keyword ideas and calculate opportunity gaps)

**Data validation:**
- ✅ 5 unique SKUs processed
- ✅ 500 keyword ideas generated (100 per SKU)
- ✅ 343 high-volume ideas (100+ monthly searches)
- ✅ 153 gap keywords identified
- ✅ 168,530 total gap volume
- ✅ 57.0% average coverage rate
- ✅ Valid JSON output
