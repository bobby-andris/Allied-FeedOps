# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation at scale
**Current focus:** Phase 17 — Google Shopping Intelligence & Model Research

## Current Position

Phase: 17 of 20 (Google Shopping Intelligence & Model Research)
Plan: 1 of TBD in current phase
Status: In progress
Last activity: 2026-02-21 — Phase 17 Plan 01 complete (Google Shopping ranking factors research)

Progress: [█░░░░░░░░░] ~5% (v1.2 milestone — 1/TBD plans complete)

## Performance Metrics

**Velocity (prior milestones for reference):**
- Total plans completed: 51 (phases 01-16)
- v1.1: 8 phases / 24 plans

| Milestone | Phases | Plans |
|-----------|--------|-------|
| Phase 0 | 4 | 11 |
| v1.0 | 4 | 16 |
| v1.1 | 8 | 24 |
| v1.2 | 4 | TBD |

## Accumulated Context

### Decisions

- [v1.2 roadmap]: Google Shopping Intelligence research (Phase 17) runs BEFORE diagnosis — ranking knowledge informs what to look for in code review
- [v1.2 roadmap]: Model research grouped with Google Shopping research in Phase 17 — both are pure research with no code dependencies
- [v1.2 roadmap]: Fixes (Phase 20) are conditional on Phase 18-19 findings — apply only fixes matched to confirmed evidence
- [17-01]: auction_insight_view not in Google Ads API v16 — use manual UI export or upgrade to v18 for competitor domain data
- [17-01]: Merchant Center account ID ≠ Google Ads customer ID — user must provide MC ID for disapproval diagnostic
- [17-01]: Feed content coverage (79/2,784 SKUs = 2.8%) is primary scale bottleneck; content quality (89.4/100 avg) is already production-ready
- [17-01]: {FINISH_NAME} placeholder found in approved content (SKU 102) — expand-variants.ts substitution bug needs immediate fix

### Key Context Carried Forward

- v1.1 completed: 8 phases, 24 plans, 16/16 requirements — phases archived to .planning/milestones/v1.1-phases/
- Feature flags exist (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1) but activation status unknown — Phase 18 audit will confirm
- Dashboard regeneration is thin proxy to Cloud Run Python pipeline — core.ts is dead code
- 824/2,784 SKUs have search term coverage; performance backfill in progress (job 3da77cd6)
- [17-01] Allied Brass campaign baseline: 179 Shopping campaigns, all Standard Shopping (not PMax), all Target ROAS, avg IS 69.7%, IS lost to rank 20.2%, budget IS loss ~0%
- [17-01] Grab bars campaign: 25,086 impressions, 1.00% CTR, 67.3% IS; "decorative grab bars" terms get 0% CTR — confirmed content quality problem
- [17-01] 9 prompt changes for Phase 20 documented in docs/research/google-shopping-ranking-factors.md
- [17-01] H1 CONFIRMED: Feed quality is primary gap. H2 PARTIALLY. H3 LIKELY CONFIRMED. H4 PARTIALLY. H5/H6/H7 UNCONFIRMED.

### Blockers/Concerns

- GMC merchant account ID needed for Phase 19 Merchant API integration (not same as Google Ads ID 6253381786) — confirmed in 17-01
- Keyword bank (data/keyword-bank.json) may be gitignored — verify in Cloud Run container during Phase 18
- Campaign type: CONFIRMED Standard Shopping (not Performance Max) — all campaigns use Standard Shopping + Target ROAS
- {FINISH_NAME} placeholder bug in expand-variants.ts — needs fix before next publish run
- Google Ads API v16 does not support auction_insight_view — need v18 upgrade or manual UI export for competitor domain data

### Pending Todos

None.

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 17-01-PLAN.md (Google Shopping ranking factors research)
Resume file: None
