# Quick Task 2: Fix 3 UAT bugs — Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Task Boundary

Fix 3 UAT bugs confirmed in docs/uat/dashboard-comprehensive-uat.md:
- Bug A: Generate tab recommends already-generated SKUs
- Bug B2: Pipeline generates 28 finish sentences for SKUs with fewer variants
- Bug B4: Review page doesn't understand which finishes apply per-SKU

</domain>

<decisions>
## Implementation Decisions

### Bug A: SKU Exclusion Scope
- Exclude ANY SKU with ANY row in `generated_content` (regardless of approval status)
- These SKUs are "in the pipeline" — any title/description changes happen on the review page
- Current code only excludes rows where `approved_content IS NOT NULL` — this is too narrow

### Bug B2: Finish Sentence Generation
- Query `variant_index` per-SKU to determine actual finishes at generation time
- Pass the real finish list to the LLM instead of hardcoded FINISH_LIST_28
- This is cleaner than generating all 28 and filtering after

### Bug B4: Review Page Validation (Reframed)
- Generating all 28 finish sentences is expected behavior — not a bug in itself
- The real fix: review page and publish pipeline must query `variant_index` to know which finishes apply
- Display only relevant finish sentences on the review page
- Publish only the finishes that exist in `variant_index` for that master SKU
- No need for a "mismatch warning" — just correctly filter by actual variants

### Claude's Discretion
- Systematic debugging approach for each bug (code reads + DB queries to prove root cause)
- Specific implementation patterns for variant_index queries

</decisions>

<specifics>
## Specific Ideas

- Bug A root cause file: `dashboard/src/app/api/sku-selection/route.ts` lines 29-36
- Bug B2 root cause: `get_finish_list()` in `prompt_loader.py` returns hardcoded `FINISH_LIST_28`; `finish_processing.py` uses it everywhere
- Bug B4: `computePlatformReadinessForSku` in `dashboard/src/lib/review/platform-progress.ts` already checks `variants` from variant_index — the issue is about finish sentence display/filtering, not readiness computation
- Test SKU: 7272D/30 (25 variants, 28 finish sentences in DB)

</specifics>
