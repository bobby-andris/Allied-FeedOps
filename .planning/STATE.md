# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation at scale
**Current focus:** Phase 17 — Google Shopping Intelligence & Model Research

## Current Position

Phase: 17 of 20 (Google Shopping Intelligence & Model Research)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-02-20 — v1.2 roadmap created, phases 17-20 defined

Progress: [░░░░░░░░░░] 0% (v1.2 milestone — 0/TBD plans complete)

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

### Key Context Carried Forward

- v1.1 completed: 8 phases, 24 plans, 16/16 requirements — phases archived to .planning/milestones/v1.1-phases/
- Feature flags exist (PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, SEGMENT_STRATEGY_V1) but activation status unknown — Phase 18 audit will confirm
- Dashboard regeneration is thin proxy to Cloud Run Python pipeline — core.ts is dead code
- 824/2,784 SKUs have search term coverage; performance backfill in progress (job 3da77cd6)

### Blockers/Concerns

- GMC merchant account ID needed for Phase 19 Merchant API integration (not same as Google Ads ID 6253381786)
- Keyword bank (data/keyword-bank.json) may be gitignored — verify in Cloud Run container during Phase 18
- Campaign type (Standard Shopping vs Performance Max) affects Phase 20 A/B options

### Pending Todos

None.

## Session Continuity

Last session: 2026-02-20
Stopped at: Roadmap created for v1.2, phases 17-20 defined, ready to plan Phase 17
Resume file: None
