# Branch Workstream Tracker — d5ea (`codex/shopping-funnel-integration-20260220`)

Last updated: 2026-02-20 (Task 7 complete: GA4+Shopify supplemental confidence gates)

## Purpose
Track progress for the 8-step Google Ads optimization implementation sequence on this branch, including what is complete, what is pending, and key implementation notes.

## Current Status Summary
- Task 1: complete
- Task 2: complete
- Task 3: complete
- Task 4: complete
- Task 5: complete
- Task 6: complete
- Task 7: complete
- Task 8: pending

## 8-Task Execution Checklist
1. **Implement decomposition pipeline v1 (deterministic parser, persistence, health/backfill ops)** — ✅ Complete
2. **Build query value scoring service v1 (expected clicks/CVR/value/profit proxy calibration)** — ✅ Complete
3. **Add profit-weighted reviewer queue defaults and high-impact filters in Shopping Funnel UI** — ✅ Complete
4. **Ship recommendation explainability panel (reason codes, confidence components, diagnostics)** — ✅ Complete
5. **Implement adaptive tROAS recommender by `custom_label_0 × tier` (recommend-only mode)** — ✅ Complete
6. **Add opportunity cluster miner v1 and launch-brief generation workflow** — ✅ Complete
7. **Integrate GA4+Shopify supplemental value signals into scoring confidence gates** — ✅ Complete
8. **Add guardrail incidents and experiment instrumentation for safe rollout decisions** — ⏳ Pending

---

## Completed Work Details

## Task 1 — Decomposition Pipeline v1 (Deterministic)
### What was implemented
- Deterministic, versioned decomposition engine (`decomp_v1`, `score_v1`, `route_v1`).
- Artifact persistence and hydration for:
  - `query_intent_features`
  - `query_value_scores`
  - `routing_recommendations`
- Pipeline orchestration in Shopping Funnel service:
  - cached read
  - stale/missing recompute
  - best-effort persistence
  - backward-compatible term-level rollup
- Operational endpoints:
  - `GET /api/optimization/decomposition/health`
  - `POST /api/optimization/decomposition/backfill`
- Additive `pipeline` metadata surfaced in optimization endpoints.
- Regression-safe behavior preserved for existing consumers.

### Key hardening completed
- Fixed Supabase URI-length (`414`) risk by chunking artifact lookup reads.

### Validation
- Decomposition unit/integration tests passed.
- Build passed.
- Tracking regression guard passed.

### Main commits
- `04a33178` — feat: add deterministic decomposition pipeline with persistence and ops endpoints
- `89776c75` — fix: chunk decomposition artifact reads to avoid supabase URI limits

## Task 2 — Query Value Scoring Service v1 (Calibrated)
### What was implemented
- New calibrated scoring module:
  - hierarchical priors (`global`, `tier`, `label`, `label+tier`)
  - deterministic smoothing for CTR/CVR/CPC/value-per-conversion
  - uncertainty and impact score derivation
- Integrated calibrated scoring into:
  - live pipeline recompute path
  - backfill path
- Added term-level aggregation from pair-level calibrated outputs.
- Added dedicated value-scoring test coverage.

### Validation
- Targeted tests passed.
- Build passed.
- Lint passed (only pre-existing warnings).

### Main commit
- `ca587cb0` — feat: add calibrated query value scoring for decomposition pipeline

## Task 3 — Profit-Weighted Queue Defaults + High-Impact Filters
### What was implemented
- Added reviewer priority scoring utility:
  - `computeReviewerPriorityScore(value_score)` based on expected profit proxy weighted by certainty.
  - `isHighImpactValueScore(...)` threshold helper for UI filtering.
- Updated recommendation queue ranking in control-center intelligence logic:
  - primary sort by `priorityScore`, fallback by `impactScore`.
- Updated Shopping Funnel “Needs Decision” UI:
  - default sort switched to `Profit priority (high to low)`.
  - added high-impact filter controls:
    - `High-impact only` toggle
    - `Min priority score` input
    - `Max uncertainty (0-1)` input
  - added `high-impact in view` badge in reviewer summary strip.
  - surfaced row-level diagnostics: `Priority` and `Uncertainty`.

### Validation
- New tests passed:
  - `src/lib/shopping-funnel/__tests__/reviewer-priority.test.ts`
- Regression tests passed:
  - `src/lib/optimization/__tests__/control-center.test.ts`
- `npm run build` passed.
- `npm run lint` passed with only existing baseline warnings.

### Next recommended step
- Proceed with **Task 4**: recommendation explainability panel enhancements (reason-code clarity + confidence component drill-down in reviewer flow).

## Task 4 — Recommendation Explainability Panel
### What was implemented
- Added structured explainability model for `NeedsDecisionTerm`:
  - parser/score/recommendation versions
  - reason codes
  - intent + recommendation confidence
  - confidence component breakdowns
  - diagnostics token breakdown and ambiguity flags
- Added explainability mapper:
  - `/dashboard/src/lib/shopping-funnel/explainability.ts`
- Enhanced decomposition engine metadata:
  - `decision_path`
  - `recommendation_confidence_components` emitted into recommendation metadata for persisted artifacts.
- Wired explainability into enrichment paths:
  - decomposition pipeline path in `shopping-funnel/service.ts`
  - fallback enrichment path in `optimization/query-intelligence.ts`
- Upgraded Shopping Funnel UI row details:
  - new explainability section per expanded term
  - reason code badges
  - confidence badges and component drill-down
  - diagnostics display (normalized term, token matches, ambiguity signals)

### Validation
- New/updated tests passed:
  - `src/lib/shopping-funnel/__tests__/explainability.test.ts`
  - `src/lib/optimization/decomposition/__tests__/engine.test.ts`
  - `src/lib/shopping-funnel/__tests__/reviewer-priority.test.ts`
  - `src/lib/optimization/__tests__/control-center.test.ts`
- `npm run build` passed.
- `npm run lint` passed with only existing baseline warnings.

### Next recommended step
- Proceed with **Task 5**: adaptive tROAS recommender by `custom_label_0 × tier` in recommend-only mode with confidence and safety caps.

## Task 5 — Adaptive tROAS Recommender (`custom_label_0 × tier`, recommend-only)
### What was implemented
- Reworked tROAS policy logic in `control-center` to an adaptive model with explicit safety bounds:
  - max weekly adjustment cap: `±10%`
  - near-target no-op band: `±8%`
  - adaptive gain-based step sizing on ROAS gap
- Added evidence-based guardrails before recommending changes:
  - minimum spend/click/conversion thresholds
  - minimum confidence threshold
  - explicit guardrail statuses:
    - `actionable`
    - `insufficient_data`
    - `near_target_band`
- Expanded recommendation payload with additive explainability fields:
  - `roasGapRatio`
  - `appliedStepPct`
  - `maxAllowedStepPct`
  - `confidenceComponents` (click/conversion/spend/final)
- Updated Optimization Control Center UI to show:
  - capped step percentage + cap value
  - guardrail status badge
  - ROAS gap percentage
  - confidence component breakdown
- Maintained recommend-only behavior (no posting/automation changes).

### Validation
- Targeted tests passed:
  - `src/lib/optimization/__tests__/control-center.test.ts` (7/7)
- Full build passed:
  - `npm run build` (Next.js production build)
- Lint passed:
  - `npm run lint` (0 errors, existing baseline warnings only)

### Main commit status
- `a904154f` — feat: ship explainability and adaptive tROAS recommendations

## Task 6 — Opportunity Cluster Miner v1 + Launch-Brief Workflow
### What was implemented
- Expanded opportunity cluster miner with overlap/cannibalization risk intelligence:
  - overlap risk score + risk level (`low`/`medium`/`high`)
  - recommendation confidence and uncertainty rollups
  - custom label dispersion and top label extraction
  - attractiveness scoring now risk-adjusted (not just impact × CPC)
- Added deterministic launch-brief generator:
  - pilot naming and priority (`high`/`medium`/`low`)
  - budget cap, observation window, target ROAS/min traffic criteria
  - negative-control guidance and stop conditions
  - buildout checklist for campaign/ad-group pilots
- Wired opportunities API to return richer launch briefs:
  - supports `account_median_roas` input for KPI threshold shaping
  - returns `launch_briefs` derived from cluster outputs
- Upgraded Optimization Control Center UI:
  - cluster cards now show overlap risk and confidence context
  - new “Launch Briefs” section with pilot-ready execution guidance
  - preserved recommend-only posture (no auto posting/create actions)

### Validation
- TDD RED→GREEN completed with new failing tests first, then implementation:
  - `src/lib/optimization/__tests__/control-center.test.ts`
- Regression test suite passed:
  - `src/lib/optimization/__tests__/control-center.test.ts`
  - `src/lib/optimization/decomposition/__tests__/engine.test.ts`
  - `src/lib/shopping-funnel/__tests__/reviewer-priority.test.ts`
  - `src/lib/shopping-funnel/__tests__/explainability.test.ts`
- `npm run lint` passed with existing baseline warnings only.
- `npm run build` passed (full Next.js production build).

### Main commit status
- Local Task 6 code is implemented and verified in the branch working tree.
- Next checkpoint commit will include Task 6 changes + tracker update.

## Task 7 — GA4+Shopify Supplemental Value Signals into Confidence Gates
### What was implemented
- Added deterministic supplemental confidence gate utility:
  - `/dashboard/src/lib/optimization/supplemental-confidence.ts`
  - consumes GA4 attribution quality + Shopify mapping coverage diagnostics.
  - computes bounded multiplier + reason codes + warnings + diagnostics.
- Integrated gate-aware queue scoring in optimization control-center logic:
  - `buildRecommendationQueue` now accepts optional supplemental gate input.
  - queue rows now include:
    - `baseConfidence`
    - gated `confidence`
    - `confidenceMultiplier`
    - `confidenceAdjustmentReasons`
- Wired `/api/shopping-funnel/recommendations` to fetch supplemental signals safely:
  - GA4: `fetchGa4AttributionQuality(...)`
  - Shopify: `fetchShopifyValueSignalsWithLabelMapping(...)`
  - failures degrade gracefully to warnings (no hard-fail on recommendations route).
- Added reusable Shopify mapping/value helper in core library:
  - `fetchCustomLabelBySku(...)`
  - `fetchShopifyValueSignalsWithLabelMapping(...)`
- Refactored `/api/shopify/value-signals` to use shared helper and keep output contract stable.
- Updated Optimization Control Center UI to expose confidence gating context:
  - shows gated confidence vs base confidence.
  - displays supplemental confidence gate reason codes.
  - ingests recommendation-route warnings into supplemental warning panel.

### Validation
- New tests passed:
  - `src/lib/optimization/__tests__/supplemental-confidence.test.ts`
- Updated tests passed:
  - `src/lib/optimization/__tests__/control-center.test.ts`
- Lint passed (existing unrelated warnings only).
- Full Next.js production build passed.

### Main commit status
- Task 7 implementation is complete in the branch working tree and ready to commit.

---

## Notes / Operational Constraints
- `SHOPPING_DECOMPOSITION_PIPELINE_ENABLED` currently controls read-path activation:
  - `false`: fallback enrichment path, no live decomposition read pipeline.
  - `true`: decomposition pipeline runs on `needs-decision` reads (with persistence unless overridden).
- Backfill `dry_run=true` remains the safe rehearsal mode and writes nothing.

## Recommended Next Step
Proceed with **Task 8**:
- add guardrail incidents and experiment instrumentation for safe rollout decisions.
- leverage existing recommendation diagnostics to trigger measurable rollout-go/no-go signals.

## Session Log (Latest)
- Implemented and verified Task 6 opportunity miner + launch brief workflow.
- Validation evidence captured:
  - targeted and regression test success
  - lint success (warnings only)
  - full production build success.
