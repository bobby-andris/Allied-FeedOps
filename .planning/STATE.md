# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation at scale
**Current focus:** Phase 19 — Measurement Infrastructure

## Current Position

Phase: 19 of 20 (Measurement Infrastructure)
Plan: 2 of 4 in current phase
Status: In progress — 19-02 complete (bottleneck classifier + prompt lineage API routes)
Last activity: 2026-02-21 — Phase 19 Plan 02 complete (POST /api/bottleneck/classify, GET /api/bottleneck/status, GET /api/prompt-lineage)

Progress: [█████░░░░░] ~22% (v1.2 milestone — 5/TBD plans complete)

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
| Phase 18-diagnosis-establish-ground-truth P02 | 4 | 2 tasks | 4 files |
| Phase 19-measurement-infrastructure P02 | 4 | 2 tasks | 3 files |
| Phase 19-measurement-infrastructure P01 | 16 | 2 tasks | 4 files |

## Accumulated Context

### Decisions

- [v1.2 roadmap]: Google Shopping Intelligence research (Phase 17) runs BEFORE diagnosis — ranking knowledge informs what to look for in code review
- [v1.2 roadmap]: Model research grouped with Google Shopping research in Phase 17 — both are pure research with no code dependencies
- [v1.2 roadmap]: Fixes (Phase 20) are conditional on Phase 18-19 findings — apply only fixes matched to confirmed evidence
- [18-01]: DIAG-02 CONFIRMED — Path A (UI regen) calls main.py::regenerate_content() via HTTP POST; generator.py::build_prompt() is bypassed (legacy 6-agent pipeline only)
- [18-01]: DIAG-03 CONFIRMED — All 3 feature flags wired to production paths, all default True (enabled), no Cloud Run overrides needed
- [18-01]: keyword_bank.json absent from Cloud Run — data/ excluded from Docker build context; external keywords always [] in production
- [17-01]: auction_insight_view not in Google Ads API v16 — use manual UI export or upgrade to v18 for competitor domain data
- [17-01]: Merchant Center account ID ≠ Google Ads customer ID — user must provide MC ID for disapproval diagnostic
- [17-01]: Feed content coverage (79/2,784 SKUs = 2.8%) is primary scale bottleneck; content quality (89.4/100 avg) is already production-ready
- [17-01]: {FINISH_NAME} placeholder found in approved content (SKU 102) — expand-variants.ts substitution bug needs immediate fix
- [Phase 17-03]: PMax Zombie SKUs (126K impressions, 54.6% IS Lost to Rank) identified as highest-value Phase 20 target — content generation priority 1
- [Phase 17-03]: Decorative grab bar CTR gap confirmed: 741 impressions at 0% CTR traced to title language mismatch — fix is adding 'Decorative' to Pipeline/Cube Design grab bar titles
- [Phase 18-02]: Separate /api/funnel/summary endpoint instead of augmenting /api/stats — avoids slowing existing stats load
- [Phase 18-02]: COUNT DISTINCT via JS Set dedup for funnel queries — Supabase JS client lacks native COUNT DISTINCT
- [Phase 18-02]: Stage 5 (confirmed_sample) reads static spot-check-results.json — live read-back is DIAG-04's job (Plan 03)
- [Phase 18-03]: DIAG-04 CONFIRMED — Propagation pipeline is working correctly; 10/10 published SKUs have structurally matching content in Google Sheets; 0 discrepancies
- [Phase 18-03]: {FINISH_NAME} in Supabase approved_content is intentional template (28 rows, 28 SKUs); expand-variants.ts correctly substitutes at publish time; not a bug requiring an immediate fix
- [Phase 18-03]: Node.js helper needed for Python Sheets access — GOOGLE_SERVICE_ACCOUNT_KEY has non-standard 2056-bit RSA modulus rejected by Python cryptography but accepted by Node.js; use fetch_sheets_data.js pattern for future Python scripts needing Sheets access
- [Phase 19-02]: Delete-then-insert for auto-classifications: Supabase JS cannot target partial unique indexes directly
- [Phase 19-02]: maybeSingle() for optional lookups in prompt-lineage to avoid 406 errors on missing rows
- [Phase 19-01]: capture_flag_snapshot() captures flags at call time (not import time) — avoids warm container stale state in Cloud Run
- [Phase 19-01]: Migration 035 created but needs manual application via Supabase SQL Editor — dev machine has no direct postgres access

### Key Context Carried Forward

- v1.1 completed: 8 phases, 24 plans, 16/16 requirements — phases archived to .planning/milestones/v1.1-phases/
- Feature flags (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1): all confirmed wired to production paths in evidence.py and prompt_loader.py — all default to True (enabled), no Cloud Run env vars override
- Dashboard regeneration is thin proxy to Cloud Run Python pipeline — core.ts is dead code
- 824/2,784 SKUs have search term coverage; performance backfill in progress (job 3da77cd6)
- [17-01] Allied Brass campaign baseline: 179 Shopping campaigns, all Standard Shopping (not PMax), all Target ROAS, avg IS 69.7%, IS lost to rank 20.2%, budget IS loss ~0%
- [17-01] Grab bars campaign: 25,086 impressions, 1.00% CTR, 67.3% IS; "decorative grab bars" terms get 0% CTR — confirmed content quality problem
- [17-01] 9 prompt changes for Phase 20 documented in docs/research/google-shopping-ranking-factors.md
- [17-01] H1 CONFIRMED: Feed quality is primary gap. H2 PARTIALLY. H3 LIKELY CONFIRMED. H4 PARTIALLY. H5/H6/H7 UNCONFIRMED.
- [17-03]: 741 decorative grab bar impressions at 0% CTR confirmed — title language mismatch ("Pipeline Collection Grab Bar" vs "Decorative Grab Bar") is the entire explanation
- [17-03]: PMax "Zombie SKUs" campaign discovered: 126,283 impressions, 54.6% IS Lost to Rank — highest IS-loss in account, not in Plan 01 analysis
- [17-03]: Phase 20 priority order confirmed by data: PMax Zombie SKUs > garment rods > retractable hooks > grab bars > paper towel holders
- [17-03]: Kingston Brass wins via Home Depot/Amazon (DA 90+) — structural gap, mitigation is superior content quality on niche/specialty search terms
- [17-03]: 15 total prompt changes for Phase 20 (9 from Plan 01 + 6 new from this plan)
- [17-02]: GPT-5.2 scored 90.0/100 vs GPT-4o baseline at 76.4/100 on same production prompt — 17.8% quality improvement confirmed
- [17-02]: GPT-4o disqualified — instruction leak observed (literal prompt text in output for 1/5 SKUs)
- [17-02]: Claude Sonnet 4.6 disqualified for production — fabricated claims in 2/5 SKUs (mounting hardware included not in evidence)
- [17-02]: All models cost under $20 for full 2,784 SKU catalog at batch pricing — cost not a selection factor
- [17-02]: Gemini 2.5 Pro strong for offline batch (87.8/100, 1M context) but 3.4x slower; not recommended for real-time generation

### Blockers/Concerns

- GMC merchant account ID needed for Phase 19 Merchant API integration (not same as Google Ads ID 6253381786) — confirmed in 17-01
- keyword_bank.json CONFIRMED absent from Cloud Run container — data/ excluded by .gcloudignore, external keywords always return [] in production (Phase 20 action item)
- Campaign type: CONFIRMED Standard Shopping (not Performance Max) — all campaigns use Standard Shopping + Target ROAS
- {FINISH_NAME} placeholder bug in expand-variants.ts — needs fix before next publish run
- Google Ads API v16 does not support auction_insight_view — need v18 upgrade or manual UI export for competitor domain data
- Migration 035 needs manual application via Supabase SQL Editor — apply supabase/migrations/035_measurement_infrastructure_schema.sql before Phase 19 measurement data will be captured

### Pending Todos

None.

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 19-01-PLAN.md (measurement infrastructure schema migration 035 + Python flag capture)
Resume file: None
