# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence
**Current focus:** v1.3b Phase 28 — Architecture Audit & Migration Triage

## Position

**Milestone:** v1.3b Architecture Validation & Data Persistence
**Phase:** 28 of 31 (Architecture Audit & Migration Triage)
**Plan:** 0 of TBD in current phase
**Status:** Ready to plan
**Last activity:** 2026-02-25 — Roadmap created (4 phases, 16 requirements mapped)

Progress: [░░░░░░░░░░] 0%

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

(None yet for v1.3b)

## Session Log

- 2026-02-25: v1.3b milestone started — Architecture Validation & Data Persistence
- 2026-02-25: Roadmap created — 4 phases (28-31), 16 requirements, 100% coverage
