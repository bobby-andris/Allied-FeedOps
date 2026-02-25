# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** — API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** — Phases 05-08 (shipped 2026-02-13)
- ✅ **v1.1 Dashboard UX & Quality** — Phases 9-16 (shipped 2026-02-21)
- ✅ **v1.2 Impact Debug & Fix** — Phases 17-22 (shipped 2026-02-21)
- ✅ **v1.3a Content Generation Excellence** — Phases 23-27 (shipped 2026-02-25)
- **v1.3b Architecture Validation & Data Persistence** — Phases 28-31 (in progress)

## Phases

<details>
<summary>Phase 0 Discovery — SHIPPED 2026-02-13</summary>

- [x] Phase 01: API Capability Validation (2/2 plans) — 2026-02-12
- [x] Phase 02: Comprehensive Data Discovery (4/4 plans) — 2026-02-12
- [x] Phase 03: Sample Testing & Analysis (3/3 plans) — 2026-02-13
- [x] Phase 04: Documentation & Decision (2/2 plans) — 2026-02-13

</details>

<details>
<summary>v1.0 Historical Data Backfill — SHIPPED 2026-02-13</summary>

- [x] Phase 05: Job Infrastructure & Foundation (4/4 plans) — 2026-02-13
- [x] Phase 06: Data Collection Pipeline (3/3 plans) — 2026-02-13
- [x] Phase 07: Data Quality & Validation (4/4 plans) — 2026-02-13
- [x] Phase 08: Monitoring & Automation (5/5 plans) — 2026-02-13

</details>

<details>
<summary>v1.1 Dashboard UX & Quality — SHIPPED 2026-02-21</summary>

- [x] Phase 9: SKU Review Revamp (3/3 plans) — 2026-02-18
- [x] Phase 10: Image Workflow Improvements (3/3 plans) — 2026-02-19
- [x] Phase 11: Performance Page Enhancements (3/3 plans) — 2026-02-19
- [x] Phase 12: Dashboard Audit & Cleanup (3/3 plans) — 2026-02-19
- [x] Phase 13: Fix Google Ads Data Sourcing (3/3 plans) — 2026-02-19
- [x] Phase 14: Complete 180-day Backfill & Monitoring Fixes (3/3 plans) — 2026-02-19
- [x] Phase 15: Google Ads Data Backfill & Monitoring Verification (3/3 plans, partial) — 2026-02-20
- [x] Phase 16: Fix Google Ads Backfill Pipeline (3/3 plans) — 2026-02-20

</details>

<details>
<summary>v1.2 Impact Debug & Fix — SHIPPED 2026-02-21</summary>

- [x] Phase 17: Google Shopping Intelligence & Model Research (3/3 plans) — 2026-02-21
- [x] Phase 18: Diagnosis — Establish Ground Truth (3/3 plans) — 2026-02-21
- [x] Phase 19: Measurement Infrastructure (4/4 plans) — 2026-02-21
- [x] Phase 20: Targeted Fixes & Intelligence Application (4/4 plans) — 2026-02-21
- [x] Phase 21: Apply Database Migrations & Update Schema Docs (1/1 plan) — 2026-02-21
- [x] Phase 22: Fix Integration Bugs & Close Documentation Gaps (2/2 plans) — 2026-02-21

</details>

<details>
<summary>v1.3a Content Generation Excellence — SHIPPED 2026-02-25</summary>

- [x] Phase 23: Foundation (2/2 plans) — 2026-02-21
- [x] Phase 24: Prompt Architecture (2/2 plans) — 2026-02-21
- [x] Phase 25: Evaluate & Iterate (5/7 plans, 2 superseded) — 2026-02-23
- [x] Phase 25.1: Prompt Architecture Research (3/3 plans) — 2026-02-24
- [x] Phase 25.2: Per-Platform Generation Architecture (2/3 plans, 1 superseded) — 2026-02-24
- [x] Phase 25.3: Prompt Rewrite from Human Feedback (3/4 plans, 1 deferred) — 2026-02-24
- [x] Phase 25.4: Production Impact Audit (1/1 plan) — 2026-02-24
- [x] Phase 26: Human Evaluation & Test Batch (2/3 plans) — 2026-02-24
- Phase 27: Prompt Optimization (empty)

**Known gaps:** EVAL-03, EVAL-05, EVAL-06 accepted as tech debt.

</details>

### v1.3b Architecture Validation & Data Persistence (In Progress)

**Milestone Goal:** Validate and prepare the data architecture so the circular feedback loop (capture, monitor, analyze, learn, optimize, repeat) can be built on a solid foundation for v1.3c and v1.4.

- [x] **Phase 28: Architecture Audit & Migration Triage** - Map complete data flow, confirm API quota sustainability, triage all 18 deferred tables, audit join chain integrity (completed 2026-02-25)
- [x] **Phase 29: Content-Performance Feedback Linkage** - Connect published content to CTR/CVR outcomes via feedback view, populate impact scores, enforce content versioning (completed 2026-02-25)
- [ ] **Phase 30: Historical Funnel Persistence** - Persist ephemeral service.ts Google Ads data into daily snapshots with trend indicators on dashboard
- [ ] **Phase 31: Schema Cleanup & End-to-End Validation** - Apply kept migrations, prune dead code, wire or remove orphaned components, validate full data loop

## Phase Details

### Phase 28: Architecture Audit & Migration Triage
**Goal**: Complete understanding of production schema state and data flow so all subsequent phases build on verified foundations
**Depends on**: Nothing (first phase of v1.3b)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05
**Success Criteria** (what must be TRUE):
  1. A data flow document exists mapping every table from Google Ads API through to dashboard actions, with dead ends explicitly marked
  2. Running `SELECT tablename FROM pg_tables WHERE schemaname = 'public'` matches the documented schema — no surprise tables, no missing tables
  3. Every one of the 18 deferred tables (035b + 034b) has a KEEP/DEFER/PRUNE decision with documented reasoning
  4. NULL rate percentages for publish_events.prompt_hash and performance_snapshots.content_version are known and documented, with a go/no-go decision for the feedback view
  5. API quota analysis confirms whether daily snapshot capture fits within Google Ads Standard Access limits
**Plans:** 3/3 plans complete
Plans:
- [ ] 28-01-PLAN.md — Data flow mapping & circular loop validation
- [ ] 28-02-PLAN.md — Migration triage (18 deferred tables)
- [ ] 28-03-PLAN.md — NULL rate audit & API quota analysis

### Phase 29: Content-Performance Feedback Linkage
**Goal**: Users can see how published content changes affected search performance for any SKU
**Depends on**: Phase 28 (schema state and NULL audit inform feedback view design)
**Requirements**: FEED-01, FEED-02, FEED-03, FEED-04
**Success Criteria** (what must be TRUE):
  1. Querying a published SKU returns baseline CTR, post-publish CTR at 7/14/30-day windows, and the computed delta — all from a single view or table
  2. Performance impact scores exist for published SKUs using diff-in-diff methodology (treated vs control cohort lift)
  3. After a publish event, search query snapshots capture which terms gained or lost impressions compared to pre-publish state
  4. New publish events cannot be created with a NULL prompt_hash — the content versioning chain is enforced
**Plans:** 3/3 plans complete
Plans:
- [ ] 29-01-PLAN.md — Schema migrations (impact scores table, snapshot columns) + prompt_hash enforcement
- [ ] 29-02-PLAN.md — Content Impact landing page + API route with 4-table join and window aggregation
- [ ] 29-03-PLAN.md — Drill-down detail page with search term deltas, control cohort, publish history

### Phase 30: Historical Funnel Persistence
**Goal**: Shopping Funnel dashboard shows historical trends instead of only live ephemeral data
**Depends on**: Phase 28 (API quota analysis confirms daily capture is safe)
**Requirements**: HIST-01, HIST-02, HIST-03
**Success Criteria** (what must be TRUE):
  1. The funnel_snapshots_daily table contains at least 7 days of historical search term tier data, persisted from the same GAQL queries service.ts runs live
  2. A Cloud Scheduler job triggers daily capture without any user intervention, and the live service.ts query path has zero latency increase
  3. The Shopping Funnel dashboard page displays 7-day vs previous-7-day trend indicators (up/down/flat) for key funnel metrics
**Plans:** 3 plans
Plans:
- [ ] 30-00-PLAN.md — Test scaffolds for capture, trends, and FunnelTrendCards (Wave 0)
- [ ] 30-01-PLAN.md — Schema creation + capture endpoint + Cloud Scheduler setup script
- [ ] 30-02-PLAN.md — Trends API route + FunnelTrendCards UI component

### Phase 31: Schema Cleanup & End-to-End Validation
**Goal**: Production schema reflects reality — no aspirational empty tables, no dead TypeScript files, no orphaned components — and the full data loop is validated end-to-end
**Depends on**: Phase 28 (triage decisions), Phase 29 (feedback tables), Phase 30 (persistence tables)
**Requirements**: MIGR-01, MIGR-02, MIGR-03, MIGR-04
**Success Criteria** (what must be TRUE):
  1. The subset of 035b tables marked KEEP are applied to production with schemas verified against their TypeScript consumers — no column mismatches
  2. TypeScript files referencing pruned tables are deleted and `npm run build` passes cleanly
  3. GmcDisapprovalBadge and PromptLineagePanel are either visible on a dashboard page or removed from the codebase
  4. SCHEMA.md accurately reflects the true production database state — every table listed exists, every existing table is listed
  5. A single SKU can be traced through the complete loop: generate content, publish, capture performance snapshot, see feedback in the content-performance view
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 28 -> 29 -> 30 -> 31

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-04 | Phase 0 | 11/11 | Complete | 2026-02-13 |
| 05-08 | v1.0 | 16/16 | Complete | 2026-02-13 |
| 09-16 | v1.1 | 24/24 | Complete | 2026-02-21 |
| 17-22 | v1.2 | 17/17 | Complete | 2026-02-21 |
| 23-27 | v1.3a | ~20/21 | Complete | 2026-02-25 |
| 28. Audit & Triage | 3/3 | Complete    | 2026-02-25 | - |
| 29. Feedback Linkage | 3/3 | Complete    | 2026-02-25 | - |
| 30. Funnel Persistence | v1.3b | 0/3 | Not started | - |
| 31. Schema Cleanup | v1.3b | 0/TBD | Not started | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone completed: 2026-02-21*
*v1.2 milestone completed: 2026-02-21*
*v1.3a milestone completed: 2026-02-25*
