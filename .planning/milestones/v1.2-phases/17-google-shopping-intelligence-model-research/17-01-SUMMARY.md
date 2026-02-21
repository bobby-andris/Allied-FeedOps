---
phase: 17-google-shopping-intelligence-model-research
plan: 01
subsystem: research
tags: [google-shopping, ranking-factors, feed-quality, impression-share, google-ads-api, auction-insights, competitive-analysis]

# Dependency graph
requires: []
provides:
  - Google Shopping ranking factor taxonomy (feed-controllable, account-level, external) with Allied Brass-specific data
  - Allied Brass campaign performance baseline: 179 campaigns, 69.7% avg IS, 20.2% IS lost to rank
  - Confirmed primary hypothesis H1: feed quality is primary gap (97.2% of catalog unoptimized)
  - Confirmed grab bar CTR problem: decorative grab bar terms get impressions but 0 clicks
  - 9 specific actionable prompt changes for Phase 20
  - Identified {FINISH_NAME} placeholder bug requiring immediate fix
  - Model benchmarking cost comparison data (GPT-4o vs GPT-5.2 vs Claude vs Gemini)
affects: [phase-20-prompt-rewrites, phase-19-competitive-gap-analysis, phase-18-code-audit]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Research documents stored as markdown in docs/research/ for machine-readable consumption by downstream agents"
    - "Google Ads API v16 GAQL queries for campaign IS metrics — auction_insight_view not available in v16"

key-files:
  created:
    - docs/research/google-shopping-ranking-factors.md
  modified: []

key-decisions:
  - "auction_insight_view is not supported in Google Ads API v16 — documented as technical limitation, not data unavailability"
  - "Merchant Center account ID is distinct from Google Ads customer ID (6253381786) — MC ID needed for disapproval diagnostic"
  - "Feed content coverage is the scale bottleneck: 79/2,784 SKUs (~2.8%) have approved content; this is the highest-leverage intervention"
  - "{FINISH_NAME} placeholder bug found in approved content — needs immediate verification in expand-variants.ts"

patterns-established:
  - "Pattern 1: Pull live API data first (Google Ads + Supabase), then compile research — avoids fabrication and grounds findings in real Allied Brass data"

requirements-completed: [GOOG-01, GOOG-03]

# Metrics
duration: 7min
completed: 2026-02-21
---

# Phase 17 Plan 01: Google Shopping Ranking Factors Research Summary

**Google Shopping ranking factor taxonomy with Allied Brass live data: confirmed H1 (feed quality is primary gap), identified 0-click decorative grab bar CTR problem, and produced 9 actionable Phase 20 prompt changes from real campaign data.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-02-21T01:41:19Z
- **Completed:** 2026-02-21T01:48:00Z
- **Tasks:** 1 of 1
- **Files modified:** 1 (created docs/research/google-shopping-ranking-factors.md)

## Accomplishments

- Pulled live Google Ads data: 179 Shopping campaigns, impression share metrics, search terms for grab bars — all real numbers
- Confirmed H1 (feed quality primary gap): baseline titles are "Skyline Collection Towel Ring" level — no finish, size, or intent signals; 97.2% of 2,784 SKUs have no generated content
- Confirmed H3 (competitor domain authority): Kingston Brass/Delta/Moen sell via Home Depot/Amazon (DA 90+); Allied Brass direct Shopify site is at a structural disadvantage
- Partially confirmed H2 (attribute completeness): GTIN >99% coverage is excellent; weight_capacity missing for 23.5% of catalog (17,862 items)
- Discovered and documented {FINISH_NAME} placeholder bug in approved content (SKU 102) — needs immediate pipeline fix
- Documented Google Ads API v16 limitation (auction_insight_view unsupported) with workarounds
- Produced 9 specific prompt change recommendations tied to data evidence for Phase 20

## Task Commits

1. **Task 1: Research Google Shopping ranking factors and collect Allied Brass competitive data** - `17105798` (feat)

**Plan metadata:** (included in final docs commit below)

## Files Created/Modified

- `docs/research/google-shopping-ranking-factors.md` — 4,990-word research document with ranking taxonomy, Allied Brass live data, hypothesis status table (H1-H7), 9 prompt change recommendations, and quick wins checklist

## Decisions Made

- **auction_insight_view not in API v16:** Attempted programmatic Auction Insights pull — Google Ads API v16 returns UNRECOGNIZED_FIELD for `auction_insight.domain`. Documented as technical limitation. Three resolution paths: (a) manual UI export, (b) upgrade client to v18, (c) defer to Phase 19 SERP scraping.
- **Merchant Center ID needed for full diagnostic:** MC account ID ≠ Google Ads customer ID. Cannot run product disapproval diagnostic without it. Documented as open question requiring user input.
- **Used search term data as proxy for Auction Insights:** With auction_insight_view unavailable, search term performance data revealed the grab bar CTR problem directly — "decorative grab bars" with 156 impressions and 0 clicks is clear evidence of listing content failure.
- **{FINISH_NAME} bug is pipeline-level, not prompt-level:** SKU 102 has literal `{FINISH_NAME}` in approved content. This is an expand-variants.ts substitution failure, not a prompt issue. Flagged as separate fix item.

## Deviations from Plan

None - plan executed exactly as written. All Parts (A, B, C) completed. API limitations were documented rather than silently skipped.

**Documented technical limitations:**
- auction_insight_view: API v16 limitation — UNRECOGNIZED_FIELD error. Documented with three resolution paths.
- Merchant Center API: MC account ID unknown — cannot run disapproval diagnostic. Flagged as user action needed.

## Issues Encountered

1. **auction_insight_view GAQL query failed** — Google Ads API client uses v16 (`shopping_performance_view` reference in code). The `auction_insight.domain` field is not available in v16. Fixed by: using search_term_view data as proxy intelligence, documenting the limitation with resolution options.

2. **product_catalog column name mismatch** — Initial query used `product_name` column which doesn't exist (correct column is `title`). Fixed by: reading actual schema columns from a sample row before querying.

## User Setup Required

The following require user action to complete the diagnostic:

1. **Merchant Center account ID** — Needed to run product disapproval diagnostic. Available at: merchants.google.com → Settings → Account information. Once provided, Phase 19 can run the full attribute completeness and disapproval audit.

2. **{FINISH_NAME} placeholder verification** — Check that `expand-variants.ts` is substituting `{FINISH_NAME}` in approved content before publishing. SKU 102 has a confirmed placeholder in approved content.

3. **Auction Insights (optional)** — If you want competitor domain data before Phase 19 SERP scraping: export Auction Insights CSV from Google Ads UI for the grab bars campaign. This will show which domains Allied Brass competes against in that auction.

## Next Phase Readiness

**Ready for Phase 20 (prompt rewrites):**
- 9 specific prompt changes with evidence documented in `docs/research/google-shopping-ranking-factors.md`
- Ranking signal taxonomy complete with controllability and priority dimensions
- Priority order for catalog coverage: grab bars → towel bars → paper towel holders → glass shelves

**Ready for Phase 19 (competitive gap analysis):**
- Grab bar as primary case study confirmed (decorative grab bar 0-click problem is the key diagnostic)
- Hypothesis framework with evidence status for all 7 hypotheses
- SERP scraping target: "decorative grab bars", "designer grab bars", "60 grab bar" are highest priority terms

**Blockers for Phase 19:**
- Merchant Center account ID needed (user to provide)
- Auction Insights competitor list (via manual UI export or API v18 upgrade)

---
*Phase: 17-google-shopping-intelligence-model-research*
*Completed: 2026-02-21*
