# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** — API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** — Phases 05-08 (shipped 2026-02-13)
- ✅ **v1.1 Dashboard UX & Quality** — Phases 9-16 (shipped 2026-02-21)
- 🚧 **v1.2 Impact Debug & Fix** — Phases 17-20 (in progress)

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

### 🚧 v1.2 Impact Debug & Fix (In Progress)

**Milestone Goal:** Diagnose why existing content generation and publishing is not producing measurable Google Shopping impact, and apply minimal evidence-backed fixes.

- [x] **Phase 17: Google Shopping Intelligence & Model Research** - Deep research into Google Shopping ranking factors and model alternatives before touching any code (completed 2026-02-21)
- [x] **Phase 18: Diagnosis — Establish Ground Truth** - Trace the end-to-end runtime path, audit feature flag wiring, and quantify SKU coverage funnel with zero or minimal code changes (completed 2026-02-21)
- [x] **Phase 19: Measurement Infrastructure** - Add feature flag logging, GMC disapproval visibility, prompt hash lineage, and bottleneck classification to make impact measurable (completed 2026-02-21)
- [ ] **Phase 20: Targeted Fixes & Intelligence Application** - Apply evidence-backed fixes to generation path, feature flag wiring, prompts, and image guidance — one fix at a time

## Phase Details

### Phase 17: Google Shopping Intelligence & Model Research
**Goal**: Establish what Google Shopping actually rewards in rankings, why competitors outperform Allied Brass products, and whether a model upgrade can improve content quality — before reviewing any code
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: GOOG-01, GOOG-02, GOOG-03, MODEL-01, MODEL-02
**Success Criteria** (what must be TRUE):
  1. A ranked checklist of Google Shopping optimization factors exists, distinguishing feed-controllable factors from account-level factors
  2. The competitive gap analysis explains why competitors appear 5x more often for relevant search terms, with specific hypotheses tied to auction dynamics, product data gaps, or bid strategy
  3. Model comparison document exists with quality benchmarks, cost per SKU, and speed metrics for GPT-5.2 (or current frontier), Claude, Gemini, and the current model — with a clear recommendation
  4. The research output is specific enough to inform what generation prompts should say differently in Phase 20
**Plans**: 3 plans
Plans:
- [ ] 17-01-PLAN.md — Google Shopping ranking factor research + Allied Brass competitive baseline data
- [ ] 17-02-PLAN.md — Model benchmarking (GPT-4o vs GPT-5.2 vs Claude vs Gemini) on real SKUs
- [ ] 17-03-PLAN.md — SERP scraping competitive gap analysis + optimization checklist

### Phase 18: Diagnosis — Establish Ground Truth
**Goal**: Answer four sequential questions with evidence: Is content reaching GMC? Which code path runs in production? Are feature flags wired to the active path? Is the SKU coverage funnel wide enough to move metrics?
**Depends on**: Phase 17
**Requirements**: DIAG-01, DIAG-02, DIAG-03, DIAG-04
**Success Criteria** (what must be TRUE):
  1. SKU coverage funnel shows exact counts at each stage: total catalog (2,784) → generated content → approved → published → confirmed in Google Sheets rows — with no ambiguity about what stage each SKU is at
  2. The single-SKU UI regeneration path is documented end-to-end, naming which Python functions execute (and which are bypassed) when a user clicks Regenerate in the dashboard
  3. Feature flag audit confirms with grep evidence whether PROMPT_CONTRACT_V2, INTENT_CURATOR_V1, and SEGMENT_STRATEGY_V1 have active call sites in the production code path — or are dead flags
  4. Propagation spot-check for 10-20 recently-published SKUs confirms whether Google Sheets rows contain the approved content from Supabase, with discrepancies documented
**Plans**: 3 plans
Plans:
- [ ] 18-01-PLAN.md — Code path tracing (Path A vs Path B) + feature flag audit with grep evidence
- [ ] 18-02-PLAN.md — SKU coverage funnel API + dashboard component on overview page
- [ ] 18-03-PLAN.md — Propagation spot-check (Supabase vs Google Sheets) + {FINISH_NAME} bug scope

### Phase 19: Measurement Infrastructure
**Goal**: Make impact measurable by adding the minimum instrumentation needed to know when fixes are working — feature flag state at generation time, GMC disapproval visibility, prompt version lineage, and a bottleneck classifier
**Depends on**: Phase 18
**Requirements**: MEAS-01, MEAS-02, MEAS-03, MEAS-04
**Success Criteria** (what must be TRUE):
  1. Each content generation records which feature flags were active, visible in regeneration_history — so future generations can be segmented by flag state
  2. The system can query GMC via Merchant API and surface disapproved or not-serving products with item-level issue detail — the silent impression killer is no longer invisible
  3. For any published SKU, the system can show which prompt version (hash) produced the live content — connecting performance outcomes to the exact generation input
  4. Each SKU with published content receives a bottleneck classification label (code-path gap, auction/bid, query relevance, coverage gap, or propagation failure) with evidence for the classification
**Plans**: 4 plans
Plans:
- [ ] 19-01-PLAN.md — Schema migrations + Python flag/cost capture (MEAS-01, MEAS-03)
- [ ] 19-02-PLAN.md — Bottleneck classifier + prompt lineage API routes (MEAS-03, MEAS-04)
- [ ] 19-03-PLAN.md — Dashboard UI: lineage panel, bottleneck badges, diagnostic page (MEAS-01, MEAS-03, MEAS-04)
- [ ] 19-04-PLAN.md — GMC disapproval sync + monitoring tab + badges (MEAS-02)

### Phase 20: Targeted Fixes & Intelligence Application
**Goal**: Apply one fix at a time based on Phase 18-19 evidence — wire generation paths correctly, activate feature flags, update prompts with Google Shopping intelligence, and implement model upgrade if benchmarks justify it
**Depends on**: Phase 19
**Requirements**: FIX-01, FIX-02, GOOG-04, GOOG-05, MODEL-03
**Success Criteria** (what must be TRUE):
  1. Single-SKU UI regeneration uses the same rich prompt construction as the batch path (segment strategy, keyword plan, gold examples) — verifiable by inspecting the prompt sent to the model for any SKU
  2. Feature flags PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 are wired to active generation code paths with observable activation — toggling a flag produces a different prompt structure
  3. Content generation prompts reflect Google Shopping ranking intelligence from Phase 17 — titles and descriptions address the ranking factors identified as feed-controllable
  4. Image generation guidance incorporates Google Shopping visual ranking factors from Phase 17 — clarity, lifestyle context, and quality signals are explicit in the generation instructions
  5. If a superior model was identified in Phase 17, a model switch is implemented in the Python pipeline with A/B quality comparison on sample SKUs before full rollout
**Plans**: 4 plans
Plans:
- [ ] 20-01-PLAN.md — Shopping intelligence YAML + loader + GPT-5.2 accuracy guardrail (MODEL-03, GOOG-04 foundation)
- [ ] 20-02-PLAN.md — Image generation guidance with collection/finish/category intelligence (GOOG-05)
- [ ] 20-03-PLAN.md — Shared prompt builder + prompt parity + feature flag observable activation (FIX-01, FIX-02, GOOG-04)
- [ ] 20-04-PLAN.md — Persistent corrections table + structured feedback UI (FIX-01 feedback)

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 01-04 | Phase 0 | 11/11 | Complete | 2026-02-13 |
| 05-08 | v1.0 | 16/16 | Complete | 2026-02-13 |
| 09-16 | v1.1 | 24/24 | Complete | 2026-02-21 |
| 17. Google Shopping Intelligence & Model Research | 3/3 | Complete    | 2026-02-21 | - |
| 18. Diagnosis — Establish Ground Truth | 3/3 | Complete    | 2026-02-21 | - |
| 19. Measurement Infrastructure | 4/4 | Complete   | 2026-02-21 | - |
| 20. Targeted Fixes & Intelligence Application | 2/4 | In Progress|  | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone completed: 2026-02-21*
*v1.2 roadmap created: 2026-02-20*
