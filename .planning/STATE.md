# Session State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-25)

**Core value:** Transform low-performing product feeds into high-converting assets with AI content generation informed by Google Shopping ranking intelligence
**Current focus:** v1.3b Architecture Validation & Data Persistence

## Position

**Milestone:** v1.3b Architecture Validation & Data Persistence
**Phase:** Not started (defining requirements)
**Status:** Defining requirements
**Last activity:** 2026-02-25 — Milestone v1.3b started

## What's Done

v1.3a Content Generation Excellence shipped 2026-02-25 (21/25 requirements, 3 EVAL gaps accepted):
- GPT-5.2 bugs fixed, per-platform v2 generation deployed, 8 skills wired
- v2 active on Cloud Run (FEEDOPS_PROMPT_VERSION=v2)
- Titles follow Robert's formula, 120/120 constraint checks pass, 80.5/100 avg self-score

## Accumulated Context

- GPT-5.2 strict JSON mode is hyper-sensitive to system prompt changes — test after each individual change
- Per-platform v2 generation architecture is solid; prompt content quality is the bottleneck
- Score model only consumed by v1 code path; v2 generate_per_platform() returns raw dicts with no quality gating
- 32 TypeScript files in dashboard/src/lib/intent/ reference 035b tables that don't exist in production
- service.ts queries 6 GAQL queries live with 2-minute cache, no historical persistence
- Empty dashboard pages: Shopping Funnel, Optimization Control, Intent Control, Search Governance, Experiment Lab

## Decisions

(None yet for v1.3b)

## Session Log

- 2026-02-25: v1.3b milestone started — Architecture Validation & Data Persistence
