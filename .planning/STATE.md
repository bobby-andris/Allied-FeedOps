# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence
**Current focus:** v1.3b Phase 29 — Content-Performance Feedback Linkage

## Position

**Milestone:** v1.3b Architecture Validation & Data Persistence
**Phase:** 29 of 31 (Content-Performance Feedback Linkage)
**Plan:** 1 of 3 in Phase 29 complete
**Status:** Phase 29 in progress — Plan 01 complete
**Last activity:** 2026-02-25 — Completed 29-01 (Schema + Publish Enforcement)

Progress: [████░░░░░░] 38%

## What's Done

v1.3a Content Generation Excellence shipped 2026-02-25 (21/25 requirements, 3 EVAL gaps accepted):
- GPT-5.2 bugs fixed, per-platform v2 generation deployed, 8 skills wired
- v2 active on Cloud Run (FEEDOPS_PROMPT_VERSION=v2)
- Titles follow Robert's formula, 120/120 constraint checks pass, 80.5/100 avg self-score

## Accumulated Context

- GPT-5.2 strict JSON mode is hyper-sensitive to system prompt changes — test after each individual change
- Score model only consumed by v1 code path; v2 has no quality gating
- 32 TypeScript files in dashboard/src/lib/intent/ reference 035b tables that don't exist in production
- service.ts queries 6 GAQL queries live with 2-minute cache, no historical persistence
- Empty dashboard pages: Shopping Funnel, Optimization Control, Intent Control, Search Governance, Experiment Lab
- 034b/035b migrations note "created out-of-band" — production schema state unknown until Phase 28 audits it
- Research recommends: regular tables over materialized views (Supabase limitations), pg_cron for DB-internal jobs, Cloud Scheduler for API calls, Knip for dead code detection, write-behind pattern for service.ts persistence

## Decisions

- 29-01: FEED-04 enforcement placed in logPublishEvent() — single point covers all publish code paths
- 29-01: prompt_hash enforcement only for status=success events — failed events don't need version tracking
- 29-01: Legacy fallback preserves prompt_hash when possible, only strips if DB error mentions it
- 29-01: performance_impact_scores schema drift resolved — table now exists in production
- 28-01: Circular flow validation included as section within data flow map (not separate doc)
- 28-01: 3 redundant shopping_performance_view query paths identified -- recommend Python consolidation
- 28-01: service.ts ephemeral cache is highest-severity gap for funnel analysis (7 GAQL, 2-min TTL, zero persist)
- 28-01: 034b GA4 tables missing from SCHEMA.md -- need production verification
- 28-02: All 4 034b GA4 tables KEEP -- active code consumer (snapshot-capture route), infrastructure-forward
- 28-02: 10 of 14 035b tables KEEP -- have 1-9 active production code consumers each
- 28-02: 4 035b tables DEFER -- intent_taxonomy_versions, sku_margin_daily, order_line_returns_daily, attribution_confidence_daily (no data pipeline)
- 28-02: Zero PRUNE -- empty tables cost nothing, infrastructure-forward bias
- 28-02: Dashboard wiring: Shopping Funnel (medium), Search Governance (low), Experiment Lab (low) in Phase 31; Intent Control and Optimization Control deferred to v1.3c
- 28-03: Feedback view GO -- 99.4% snapshot-to-publish_event linkage, prompt_hash backfillable from generated_content (82.9%)
- 28-03: performance_impact_scores table does not exist in production (schema drift from SCHEMA.md)
- 28-03: Daily snapshot capture SUSTAINABLE -- ~187 req/day vs 15,000 limit (1.2% utilization)
- 28-03: service.ts is most wasteful API consumer -- recommend write-behind caching in Phase 30

## Session Log

- 2026-02-25: v1.3b milestone started — Architecture Validation & Data Persistence
- 2026-02-25: Roadmap created — 4 phases (28-31), 16 requirements, 100% coverage
- 2026-02-25: Completed 28-01 — Data flow map with 10 Mermaid diagrams, circular loop validated
- 2026-02-25: Completed 28-02 — Migration triage: 18 tables, 14 KEEP, 4 DEFER, 0 PRUNE
- 2026-02-25: Completed 28-03 — NULL audit (GO for feedback view) + API quota (SUSTAINABLE at 1.2%)
- 2026-02-25: Phase 28 complete — all 3 plans executed, all 5 AUDIT requirements addressed
- 2026-02-25: Completed 29-01 — Schema creation + prompt_hash enforcement + snapshot capture wiring
