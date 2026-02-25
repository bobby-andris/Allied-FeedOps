# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** — API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** — Phases 05-08 (shipped 2026-02-13)
- ✅ **v1.1 Dashboard UX & Quality** — Phases 9-16 (shipped 2026-02-21)
- ✅ **v1.2 Impact Debug & Fix** — Phases 17-22 (shipped 2026-02-21)
- 🚧 **v1.3a Content Generation Excellence** — Phases 23-27 (in progress)

## Phases

<details>
<summary>✅ Phase 0 Discovery — SHIPPED 2026-02-13</summary>

- [x] Phase 01: API Capability Validation (2/2 plans) — 2026-02-12
- [x] Phase 02: Comprehensive Data Discovery (4/4 plans) — 2026-02-12
- [x] Phase 03: Sample Testing & Analysis (3/3 plans) — 2026-02-13
- [x] Phase 04: Documentation & Decision (2/2 plans) — 2026-02-13

</details>

<details>
<summary>✅ v1.0 Historical Data Backfill — SHIPPED 2026-02-13</summary>

- [x] Phase 05: Job Infrastructure & Foundation (4/4 plans) — 2026-02-13
- [x] Phase 06: Data Collection Pipeline (3/3 plans) — 2026-02-13
- [x] Phase 07: Data Quality & Validation (4/4 plans) — 2026-02-13
- [x] Phase 08: Monitoring & Automation (5/5 plans) — 2026-02-13

</details>

<details>
<summary>✅ v1.1 Dashboard UX & Quality — SHIPPED 2026-02-21</summary>

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
<summary>✅ v1.2 Impact Debug & Fix — SHIPPED 2026-02-21</summary>

- [x] Phase 17: Google Shopping Intelligence & Model Research (3/3 plans) — 2026-02-21
- [x] Phase 18: Diagnosis — Establish Ground Truth (3/3 plans) — 2026-02-21
- [x] Phase 19: Measurement Infrastructure (4/4 plans) — 2026-02-21
- [x] Phase 20: Targeted Fixes & Intelligence Application (4/4 plans) — 2026-02-21
- [x] Phase 21: Apply Database Migrations & Update Schema Docs (1/1 plan) — 2026-02-21
- [x] Phase 22: Fix Integration Bugs & Close Documentation Gaps (2/2 plans) — 2026-02-21

</details>

### v1.3a Content Generation Excellence (In Progress)

**Milestone Goal:** Fix content quality at its source — repair GPT-5.2 integration bugs, establish gold standards and a differentiation-first quality rubric, rewrite prompts as creative briefs, wire all 8 runtime configs, and validate with human evaluation across 10 representative SKUs.

**Requirements:** 21/25 satisfied. Remaining: EVAL-03, EVAL-04, EVAL-05, EVAL-06.

<details>
<summary>✅ Phase 23: Foundation — completed 2026-02-21</summary>

**Goal:** Fix GPT-5.2 integration bugs, create gold standards, rewrite quality rubric.
**Requirements:** GPT52-01 through GPT52-05, GOLD-01 through GOLD-04 (all satisfied)
**Plans:** 2/2 complete
- [x] 23-01-PLAN.md — Fix 5 GPT-5.2 integration bugs
- [x] 23-02-PLAN.md — Load 15 gold standards, replace self_score with 10-criterion rubric

</details>

<details>
<summary>✅ Phase 24: Prompt Architecture — completed 2026-02-21</summary>

**Goal:** Rewrite SYSTEM_PROMPT as creative brief, wire all 8 YAML configs, expand category guidance.
**Requirements:** PRMT-01 through PRMT-05 (all satisfied)
**Plans:** 2/2 complete
- [x] 24-01-PLAN.md — Rewrite SYSTEM_PROMPT, build skill loader, wire into prompt_builder
- [x] 24-02-PLAN.md — Expand category guidance to 20+ categories, add customer/competitive blocks

</details>

<details>
<summary>✅ Phase 25: Evaluate & Iterate — completed 2026-02-23</summary>

**Goal:** Validate pipeline with human evaluation across 10 SKUs, iterate on failures.
**Requirements:** EVAL-01, EVAL-02 (satisfied). EVAL-03 through EVAL-06 deferred to remaining phases.
**Plans:** 5/5 active plans complete (2 superseded)
- [x] 25-01-PLAN.md — Regenerate 10 SKUs, build blind A/B comparison
- [x] 25-02-PLAN.md — Round 1 human evaluation (FAIL: 0/10 titles, 6/10 desc)
- [x] 25-04-PLAN.md — Gap closure: prompt refactoring (skills as authority, finish in titles)
- [x] 25-05-PLAN.md — Round 2 human evaluation (FAIL: 4/10 titles, 6/10 desc consensus)
- [x] 25-06-PLAN.md — Skill updates (competitor prohibition, Robert's title formula, evidence exclusion, 6 SYSTEM_PROMPT prohibitions)
- ~~25-03-PLAN.md~~ — Publish to Google Sheets (deferred to Phase 26)
- ~~25-07-PLAN.md~~ — Round 3 evaluation (superseded by Phase 25.3)

</details>

<details>
<summary>✅ Phase 25.1: Prompt Architecture Research — completed 2026-02-24</summary>

**Goal:** Investigate why GPT-5.2 produces keyword-stuffed, filler-heavy content. Audit prompt for anti-patterns, design new architecture.
**Status:** Audit + architecture done. A/B test revealed deeper GPT-5.2 adherence problems -> spawned Phase 25.2.
**Plans:** 3/3 complete
- [x] 25.1-01-PLAN.md — Internal audit: 57K tokens, 12 contradictions, 2.7/10 anti-pattern score
- [x] 25.1-02-PLAN.md — New CTCO prompt architecture (8.2K chars, zero contradictions)
- [x] 25.1-03-PLAN.md — A/B test (C_Optimized wins structure, fails constraints)

</details>

<details>
<summary>✅ Phase 25.2: Per-Platform Generation Architecture — completed 2026-02-24</summary>

**Goal:** Per-platform generation (separate calls for Google, Bing, Shopify, finish sentences) with strict JSON schemas and feature flag.
**Plans:** 2/2 core plans complete (validation plan superseded by 25.3)
- [x] 25.2-01-PLAN.md — Per-platform schemas, platform-specific prompts, test harness
- [x] 25.2-02-PLAN.md — Wire per-platform generation into pipeline with FEEDOPS_PROMPT_VERSION flag
- ~~25.2-03-PLAN.md~~ — Full validation (superseded by Phase 25.3 end-to-end validation)

</details>

<details>
<summary>✅ Phase 25.3: Prompt Rewrite from Human Feedback — completed 2026-02-24</summary>

**Goal:** Rewrite per-platform system prompts as GPT-5.2 creative briefs based on Bobby/Robert's Round 2 feedback. Fix prompt contract drift.
**Plans:** 3/3 core plans complete (deploy plan deferred to Phase 27)
- [x] 25.3-01-PLAN.md — Cherry-pick Codex changes (JSON parser, skill sanitizer, enrichment fix)
- [x] 25.3-02-PLAN.md — Rewrite all 4 platform prompts as GPT-5.2 creative briefs (~8-10K system prompt)
- [x] 25.3-03-PLAN.md — Fix prompt contract drift, harness wiring, guardrail tests (120/120 checks pass)
- ~~25.3-04-PLAN.md~~ — Deploy v2 to production (deferred to Phase 27)

**Key result:** Automated constraint checks pass (120/120 canonical, 63/63 unseen). Human review pending.

</details>

<details>
<summary>✅ Phase 25.4: Production Impact Audit — completed 2026-02-24</summary>

**Goal:** Audit all v1-path-affecting source code changes. Align Score model with 10-criterion rubric.
**Requirements:** AUDIT-01 through AUDIT-05 (all satisfied)
**Plans:** 1/1 complete
- [x] 25.4-01-PLAN.md — Score model alignment, 3 test fixes, v1 regression tests, audit report

</details>

### Remaining Work

**Current state:** v2 per-platform generation is fully built and passes automated checks. Production runs v1 safely behind feature flag. All code is pushed to master.

**What's left for v1.3a:**

- [ ] **Phase 26: Human Evaluation & Test Batch** — Bobby/Robert gut-check review of v2 output, publish test batch
- [ ] **Phase 27: Production Deploy** — Set FEEDOPS_PROMPT_VERSION=v2, close milestone

## Phase Details

### Phase 26: Human Evaluation & Test Batch

**Goal:** Validate v2 content quality with Bobby and Robert. If it passes (8/10 consensus), publish a test batch to Google Sheets to start measuring CTR/CVR delta.
**Depends on:** All code work complete (Phases 23-25.4)
**Requirements:** EVAL-03, EVAL-04, EVAL-05, EVAL-06

**What happens:**
1. Generate 10 test SKUs using v2 pipeline (same SKUs as Round 1+2: 1025U, 1016, 102, 1020-3, 1024, 1020, DMF-2/2X, WP-2/16-GAL, 1098, CL-22)
2. Build blind A/B comparison (v1 production vs v2)
3. Bobby + Robert review — success gate: 8/10 consensus wins for both titles AND descriptions
4. If pass: run numeric quality scoring (target >85% avg), publish test batch to Google Sheets
5. If fail: analyze feedback, determine if fixable (iterate) or fundamental (rethink)

**Known risks:**
- v2 Score model wiring may need fixing (self_score -> Score model parsing in generate_per_platform)
- shopping_intelligence may not be wired into v2 per-platform builders (PRMT-03 regression check)
- These are quick code fixes, not architecture work — fix during execution if found

**Plans:** 2/3 plans executed

Plans:
- [ ] 26-01-PLAN.md — Generate 10 test SKUs with v2, compute quality scores, build blind A/B comparison
- [ ] 26-02-PLAN.md — Human evaluation checkpoint + publish test batch (if passed)

### Phase 27: Production Deploy

**Goal:** Activate v2 in production, verify it works, close v1.3a milestone.
**Depends on:** Phase 26 (8/10 human eval threshold met)
**Requirements:** (milestone closure)

Tasks:
- Set FEEDOPS_PROMPT_VERSION=v2 in Cloud Run environment variables
- Verify production generation uses v2 path (smoke test with real SKU)
- Run `/gsd:audit-milestone` to confirm 25/25 requirements satisfied
- Run `/gsd:complete-milestone v1.3a` to archive

Plans:
- [ ] 27-01-PLAN.md — TBD (plan phase before execution)

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 01-04 | Phase 0 | 11/11 | Complete | 2026-02-13 |
| 05-08 | v1.0 | 16/16 | Complete | 2026-02-13 |
| 09-16 | v1.1 | 24/24 | Complete | 2026-02-21 |
| 17-22 | v1.2 | 17/17 | Complete | 2026-02-21 |
| 23 | v1.3a | 2/2 | Complete | 2026-02-21 |
| 24 | v1.3a | 2/2 | Complete | 2026-02-21 |
| 25 | v1.3a | 5/5 | Complete | 2026-02-23 |
| 25.1 | v1.3a | 3/3 | Complete | 2026-02-24 |
| 25.2 | v1.3a | 2/2 | Complete | 2026-02-24 |
| 25.3 | v1.3a | 3/3 | Complete | 2026-02-24 |
| 25.4 | v1.3a | 1/1 | Complete | 2026-02-24 |
| 26 | 2/3 | In Progress|  | - |
| 27 | v1.3a | 0/? | Not Started | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone completed: 2026-02-21*
*v1.2 milestone completed: 2026-02-21*
*v1.3a roadmap created: 2026-02-21*
*v1.3a roadmap cleaned: 2026-02-24 — consolidated completed phases, removed duplicate/superseded phases (25.5-25.7), renumbered remaining to 26-27*
