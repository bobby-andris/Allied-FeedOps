---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-02-26T04:57:36.166Z"
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 23
  completed_plans: 22
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** Transform low-performing product feeds into high-converting assets through data-driven content optimization at scale
**Current focus:** Phase 34.2 — Zero-Conversion Intent Scoring

## Current Position

Phase: 34.2 (v1.3c) — IN PROGRESS
Plan: 1 of 3 complete
Status: Completed 34.2-01 (constrain-to-demote terminology cleanup + targetTier)
Last activity: 2026-02-26 — Completed 34.2-01: Eradicate constrain, add targetTier

Progress: [###-------] 33% (Phase 34.2)

## Performance Metrics

**Velocity:**
- Total plans completed: ~101 (across all milestones)
- Average duration: varies by complexity
- Total execution time: ~13 days (2026-02-12 to 2026-02-25)

**By Milestone:**

| Milestone | Phases | Plans | Shipped |
|-----------|--------|-------|---------|
| Phase 0 | 4 | 11 | 2026-02-13 |
| v1.0 | 4 | 16 | 2026-02-13 |
| v1.1 | 8 | 24 | 2026-02-21 |
| v1.2 | 6 | 17 | 2026-02-21 |
| v1.3a | ~8 | ~20 | 2026-02-25 |
| v1.3b | 5 | 13 | 2026-02-25 |
| Phase 34 P01 | 3min | 3 tasks | 3 files |
| Phase 34 P02 | 4min | 3 tasks | 6 files |
| Phase 34 P03 | 5min | 3 tasks | 8 files |
| Phase 34 P04 | 5min | 4 tasks | 7 files |
| Phase 34.1 P01 | 4min | 3 tasks | 3 files |
| Phase 34.1 P02 | 5min | 3 tasks | 8 files |
| Phase 34.1 P03 | 6min | 3 tasks | 9 files |
| Phase 35 P01 | 6min | 3 tasks | 6 files |
| Phase 35 P03 | 5min | 2 tasks | 5 files |
| Phase 35 P02 | 5min | 2 tasks | 11 files |
| Phase 34.2 P01 | 9min | 3 tasks | 10 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v1.3b]: Cloud Scheduler activation deferred as tech debt (OPS-01 resolves this)
- [v1.3b]: funnel_snapshots_daily needs re-backfill (OPS-02 resolves this)
- [v1.3c research]: Use simple-statistics (30KB) over mathjs (700KB) for all statistical computation
- [v1.3c research]: Background computation preferred over on-demand to avoid Vercel timeout at ~3K terms
- [v1.3c research]: Show revenue estimate ranges from day 1, never point values
- [v1.3c research]: Robust z-scores (median/MAD) over standard z-scores for right-skewed ROAS data
- [Phase 33-02]: Used createAdminClient for API route DB writes (service role needed for upsert)
- [Phase 33-02]: Client-side customLabel0 filtering for getLabelTierPerformance (function doesn't accept that param)
- [Phase 33-01]: Robust z-scores use median/MAD — ROAS capped at p99, tier fit weighted 50% ROAS / 20% CVR / 15% CPC / 15% CTR
- [Phase 33-01]: MAD=0 returns z-score 0 (handles all-identical-values edge case gracefully)
- [Phase 33-03]: Used Target icon for sidebar (BarChart3 already used by Performance)
- [Phase 33-03]: Attention-needed sorting: primary misplaced count, secondary dollar impact
- [Phase 33-03]: DistributionChart 3-zone stacked bar: orange (below p25), tier-color (healthy), blue (above p75)
- [Phase 33.1-01]: ROAS-based impact (spend * ROAS_delta) replaces broken CVR-based formula that produced $0
- [Phase 33.1-01]: CalibrationConfig centralizes thresholds: minFitScoreDelta=0.3, minConfidence=0.40, minImpressions=50
- [Phase 33.1-01]: Three-gate isMisplaced: all three thresholds must pass to flag a term
- [Phase 33.1-02]: Keep isMisplaced boolean and variable names unchanged; only change user-facing text to "opportunity"
- [Phase 33.1-02]: Show "Data-confirmed" vs "Aligned" based on dataConfirmed flag for well-placed terms
- [Phase 33.2-01]: Shared formatDollars in @/lib/formatting (consolidated from 6 copies)
- [Phase 33.2-01]: useTierScoring hook returns { data, loading, error, refresh } for reuse across views
- [Phase 33.2-01]: Verdicts use premium/mid-tier/budget labels instead of HIGH/MEDIUM/LOW
- [Phase 33.2]: Action queue components are pure presentation — no scoring engine changes
- [Phase 33.2-03]: Separate navigation state per tab (switching tabs preserves context)
- [Phase 33.2-03]: Action Queue default tab; no URL persistence for tab state (transient)
- [Phase 34-01]: Upsert on (search_term, custom_label_0) unique constraint for idempotent approve/reject
- [Phase 34-01]: Metadata JSONB stores currentTier, impact, and append-only history array for audit
- [Phase 34-01]: recommended_action defaults to 'funnel'; supports 'global_block' for wasted spend blocks
- [Phase 34-02]: Wasted spend threshold $5 (5M micros) — below is noise, not actionable
- [Phase 34-02]: Classification priority: wasted_spend > under_invested > misplaced
- [Phase 34-02]: Hook uses searchTerm::customLabel0 composite key matching API unique constraint
- [Phase 34-03]: Pure CSS box plot over Recharts custom shapes for ROAS distributions
- [Phase 34-03]: Export helper functions from components for direct unit testing
- [Phase 34-03]: ApproveOptions type extends approve callback for wasted_spend Block/Demote actions
- [Phase 34-04]: Controlled Tabs state for programmatic tab switching from HeroSummary button
- [Phase 34-04]: Extracted groupHistoryByDay as pure function for independent unit testing
- [Phase 34-04]: Undo in History tab only for accepted entries (rejected don't need undo)
- [Phase 34.1-01]: Wasted spend override: block for HIGH tier, constrain for MEDIUM/LOW (never promote)
- [Phase 34.1-01]: CPC asymmetric penalty: max(0, zCpc) — cheap CPC neutral, expensive penalized
- [Phase 34.1-01]: New TermScore fields optional to avoid breaking 15+ consumers
- [Phase 34.1-01]: verdict field now matches prescriptive actionReason text
- [Phase 34.1-02]: Under-invested uses totalImpressions for genuine impression gap detection
- [Phase 34.1-02]: Constrain button hidden at HIGH tier (no-op action)
- [Phase 34.1-02]: actionReason takes priority over verdict for display with fallback
- [Phase 34.1-02]: estimateTierFromMetrics deprecated, wasted-spend guard added
- [Phase 34.1-02]: buildRoasRecommendations wasted-spend override raises target to constrain
- [Phase 34.1-03]: Label blocks use __LABEL_BLOCK__ sentinel with action_scope='label'
- [Phase 34.1-03]: Search candidate thresholds: ROAS > 3.0, impressions > 100, conversions > 0
- [Phase 34.1-03]: funnel_snapshots_daily is correct table name (not label_tier_daily_snapshot)
- [Phase 34.1-03]: Block Label uses window.confirm for destructive action confirmation
- [Phase 35-01]: In-memory join: search_queries lacks custom_label_0, joined through query_value_scores lookup map
- [Phase 35-01]: Keyword enrichment: merge search_queries.avg_monthly_searches with keyword_metrics for best coverage
- [Phase 35-01]: BCG classification: dynamic medians from computeMedians(), not hardcoded thresholds
- [Phase 35-01]: Detail drill-down approximates quadrant locally (exact requires global medians)
- [Phase 35-03]: Quadrant legend as inline flex row below chart (not overlaid in corners) for readability
- [Phase 35-03]: fetchGroupDetail passed as callback prop to slide-out for centralized data fetching
- [Phase 35-03]: View toggle uses Button group (secondary/ghost) inline with CardHeader
- [Phase 35-02]: Color coding: green/amber/red at 50%/20% for impression share, 20%/0% for CPC headroom
- [Phase 35-02]: SeasonalTrendsChart limits to 10 lines max for readability with Keyword Planner empty state
- [Phase quick-3]: determineAction returns {action, targetTier} tuple using ROAS p25/p75 instead of statistical best-fit tier
- [Phase 34.2-01]: Replaced all 'constrain' with 'demote' — zero tolerance across types, logic, tests, UI
- [Phase 34.2-01]: targetTier optional field on TermScore, populated by determineAction()
- [Phase 34.2-01]: Domain comments use 'restricted' instead of 'constrained' for bidding behavior

### Pending Todos

- ~~Apply migration 038 (unique index on query_value_scores) to production Supabase~~ DONE
- [Phase 33.1]: Investigate $0 impact bug in estimateImpact()
- [Phase 33.1]: Calibrate scoring to reduce 95% misplaced rate to 10-20%
- [Phase 33.1]: Account for gut-assigned tiers (Robert's manual assignments, no historical data basis)
- ~~[Phase 33.2]: Redesign UI from statistical exploration to action-oriented decision-making~~ DONE
- ~~[Phase 34]: Apply migration 039 (routing_recommendations table) to production Supabase~~ DONE
- [Phase 34.1-03]: Apply migration 040 (action_scope column + label_block) to production Supabase

### Roadmap Evolution

- Phase 34.1 inserted after Phase 34: Fix Decision Logic (URGENT) — scoring engine recommends 0.0 ROAS terms move HIGH→LOW, which is backwards
- Phase 34.1 scope expanded: custom_label_0-level blocking, Shopping→Search promotion pipeline, cross-category insights

### Blockers/Concerns

- [Phase 33+]: Verify Vercel plan tier — v1.3c needs 4 cron entries (Hobby: 2, Pro: 40)
- [Phase 33+]: Validate actual ROAS distribution skewness before committing to percentile-only approach

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 3 | Fix determineAction to use ROAS-based logic instead of recommendedTier direction | 2026-02-26 | df6ed49a | [3-fix-determineaction-to-use-roas-based-lo](./quick/3-fix-determineaction-to-use-roas-based-lo/) |

## Session Continuity

Last session: 2026-02-26
Stopped at: Completed 34.2-01-PLAN.md (constrain-to-demote cleanup + targetTier)
Resume file: .planning/phases/34.2-zero-conversion-intent-scoring/34.2-01-SUMMARY.md

**Phase 33 Completion Summary**:
- Completed all 4 plans for tier scoring engine phase
- Built: Tier scoring calculation engine, tier intelligence API, UI page with 4-level drill-down, individual term scorecards
- User approved overall infrastructure; identified calibration and UI redesign follow-ups for 33.1 and 33.2
- Key finding: 95% misplaced term rate and $0 impact values indicate need for tier threshold calibration and/or impact formula review
