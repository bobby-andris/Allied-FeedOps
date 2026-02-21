---
phase: 13-fix-google-ads-data-sourcing-variant-metrics-from-shopping-performance-view-and-per-campaign-search-terms-sync
plan: 01
subsystem: google-ads-integration
tags: [diagnosis, search-terms, performance-metrics, data-quality, google-ads]
dependency_graph:
  requires: []
  provides: [13-DIAGNOSIS.md, bug-root-causes, fix-specification]
  affects: [13-02-PLAN.md, 13-03-PLAN.md]
tech_stack:
  added: []
  patterns: [empirical-first-diagnosis, code-trace-before-fix]
key_files:
  created:
    - .planning/phases/13-fix-google-ads-data-sourcing-variant-metrics-from-shopping-performance-view-and-per-campaign-search-terms-sync/13-DIAGNOSIS.md
  modified: []
decisions:
  - "Bug 1 confirmed: fetch_search_terms() line 602 uses item_ids[0] for all search terms in a campaign — attributes all terms to the single highest-impression variant instead of fan-out across all variants"
  - "Bug 2 ruled out: performance_baselines non-zero for all 5 published SKUs tested — lowercase offer IDs work correctly with Google Ads API"
  - "performance_baselines do NOT need re-capture — only search_queries needs delete + re-sync"
  - "Fix approach: fan-out per variant in fetch_search_terms(), per-SKU delete before re-insert, add synced_at column"
  - "Additional finding: item_ids in search_queries shows campaigns contain products from multiple master_skus — fix must filter to target SKU variants only"
metrics:
  duration: 4 minutes
  completed_date: 2026-02-19
  tasks: 2
  files: 1
---

# Phase 13 Plan 01: Diagnosis Summary

Diagnosed both reported Google Ads data sourcing bugs using code trace + empirical Supabase queries: confirmed Bug 1 is real (search term variant attribution uses `item_ids[0]`, assigning all terms to the highest-impression variant instead of all variants in the campaign), and ruled out Bug 2 (performance baselines are non-zero for all 5 tested published SKUs, confirming lowercase offer IDs work correctly with the API).

## Key Findings

### Bug 1: Search Terms Variant Attribution (CONFIRMED)

**Precise location:** `src/feedops/integrations/google_ads_search_terms.py`, line 602:
```python
gmc_offer_id = item_ids[0]  # BUG: always the highest-impression variant
```

**Root cause:** `_fetch_campaign_products()` returns products ordered by impressions DESC. For each search term, `fetch_search_terms()` picks `item_ids[0]` — the most-impressed variant of the campaign — and attributes ALL search terms in that campaign to it. A product with 28 finishes in a campaign will have every search term attributed to whichever finish has the most historical impressions.

**Empirical confirmation:**
- FR-23: 28 variants, only **1** distinct gmc_offer_id in search_queries (UNL/Unlacquered Brass)
- A-20: 28 variants, only **1** distinct gmc_offer_id
- CL-22: 28 variants, only **1** distinct gmc_offer_id
- CL-11: 28 variants, only **2** distinct gmc_offer_ids
- CL-24C: 28 variants, only **3** distinct gmc_offer_ids

Every search term for FR-23 is attributed to UNL, even finish-agnostic queries like "pull out valet rod closet".

### Bug 2: Performance Metrics Offer ID Case (RULED OUT)

**Hypothesis:** lowercase `shopify_us_*` offer IDs in the GAQL WHERE clause might not match, causing zero-impression baselines.

**Empirical result:** All 5 published SKUs have non-zero baselines:
- FR-23: avg_impressions=447.77 (high-traffic SKU)
- CL-24C: avg_impressions=618.37 (highest in sample)
- CL-11: avg_impressions=475.30
- CL-22: avg_impressions=222.70
- A-20: avg_impressions=67.23

**Conclusion:** Google Ads API accepts lowercase offer IDs. Phase 0 Decision #4 was correct. No fix needed for performance collection.

## Files in Fix Specification (for Plans 2 + 3)

| File | Change Required |
|------|----------------|
| `src/feedops/integrations/google_ads_search_terms.py` | Replace `item_ids[0]` with iteration over all matching item_ids, filtered to target SKU's variants |
| `src/feedops/jobs/workers.py` | Add per-SKU delete before re-insert + `synced_at` timestamp support |
| `supabase/migrations/NNN_add_synced_at_to_search_queries.sql` | Add `synced_at` column |
| `docs/database/SCHEMA.md` | Document `synced_at` column |

## Performance Baselines Decision

**performance_baselines do NOT need re-capture.** The data is correct (non-zero, appropriate ranges). Only `search_queries` needs the per-SKU delete + re-sync treatment.

## Process Retrospective Summary

Phase 0 documented the campaign-join pattern correctly but did not specify what to do when a campaign has multiple products. Phase 6 implemented `item_ids[0]` as a shortcut that is structurally valid but semantically wrong. Phase 7 validation checked data structure integrity but not semantic correctness (e.g., whether finish_code "UNL" on a query "antique brass towel bar" is correct). The bug was invisible until the dashboard made variant-level breakdown meaningful.

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Code trace — identify both bugs precisely | da24612f | 13-DIAGNOSIS.md (created) |
| 2 | Empirical data comparison using Supabase | dadc63c2 | 13-DIAGNOSIS.md (empirical section) |

## Self-Check: PASSED

- [x] 13-DIAGNOSIS.md exists at correct path
- [x] da24612f commit verified in git log
- [x] dadc63c2 commit verified in git log
- [x] All 5 verification criteria from plan met
