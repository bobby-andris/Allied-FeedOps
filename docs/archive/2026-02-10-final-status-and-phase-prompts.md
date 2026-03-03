# Final Status + Remaining Phase Prompts

## 1) Parity Matrix Confirmation (Phase 1)

The full TS-to-Python parity matrix is present in:
- `docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`

It includes all rows requested:

| TS Source | Behavior | Python Target | Decision | Phase 1 Status |
|---|---|---|---|---|
| `prompts.ts` | Balanced quality-first vs pain-point-first framing | `pipeline/prompts.py` system prompt guidance | `adopt` | implemented |
| `prompts.ts` | No hallucination / evidence-only claims | `pipeline/prompts.py` + validators | `adopt` | implemented |
| `prompts.ts` | Search-query usage guardrails | `pipeline/prompts.py` + evidence/keyword pipeline | `adapt` | implemented (pipeline wording differs) |
| `prompts.ts` | Google/Bing variant context vs Shopify master context | `_build_generation_user_prompt` in `api/main.py` | `adopt` | implemented |
| `prompts.ts` | Shopify title forbids finish + brand | `keyword_placement.py` + prompt rules | `adopt` | implemented |
| `prompts.ts` | 28 canonical finish vocabulary | `prompt_loader.py:get_finish_list` + `hybrid_generation.py` | `adopt` | implemented |
| `prompts.ts` | Bing anti-stuffing/synonym rules | `pipeline/prompts.py` constraints | `adopt` | implemented |
| `prompts.ts` | TS `validateGeneratedContent` hard checks | Python validation stack | `adapt` | partially implemented (full consolidation in later phase) |
| `core.ts` | Build enhanced prompt from evidence + examples + category guidance | `_build_generation_user_prompt` + `prompt_loader.py` helpers | `adopt` | implemented |
| `core.ts` | Simple fallback prompt path when catalog unavailable | API fallback path in Python | `adopt` | implemented |
| `core.ts` | Variant description JSON contract with `finish_sentences` map | Python generation contract | `adapt` | implemented in Phase 2 (`/regenerate` returns optional `finish_sentences`) |
| `core.ts` | Prompt hashing for traceability | `get_system_prompt_hash` + DB write fields | `adapt` | implemented (canonical prompt hash) |
| `core.ts` | TS-side OpenAI direct generation behavior | Python Cloud Run runtime only | `drop` | implemented for regeneration path in Phase 2 |
| `route.ts` | Thin proxy from dashboard to Cloud Run | `dashboard` API route -> Python `/regenerate` | `adopt` | implemented |
| `route.ts` | TS-side finish sentence OpenAI call | Python finish sentence pipeline | `drop` | implemented in Phase 2 |
| `route.ts` | Feedback presets + feedback-mode mapping | route request shaping + Python feedback field | `adapt` | implemented |
| `route.ts` | Synthetic timestamp-based prompt hash | canonical hash from Python prompt loader | `drop` | implemented |

## 2) Implementation State (from master plan execution log)

Completed in ledger:
- Phase 0 baseline verification + live canary wiring
- Phase 1 prompt-source unification + prompt hash traceability
- Phase 2 dashboard proxy/unification
- Phase 3 finish sentence validation/persistence
- Phase 4 keyword alignment + anti-stuffing + scoring guardrails
- Phase 5 evidence integration + safety constraints + verification gates
- Phase 6 dashboard production readiness hardening
- Phase 7 observability/reliability/performance hardening

## 3) Remaining Work To Fully Complete Master Plan

### Phase 8
- Scale runbook for 72k SKUs and stop-condition controls.

### Browser/UAT Validation (recommended gate before and after Phase 8)
- Full browser-driven dashboard walkthrough using `agent-browser`.
- Validate one real SKU generation path end-to-end (generate -> review -> publish-readiness checks).
- Confirm Python single-source-of-truth behavior in generated artifacts (prompt hash/model traceability + content quality checks).

## 4) Should you use Plan Mode?

Recommendation:
- **No** for direct implementation tasks in this repo (stay in default mode and execute).
- Use plan mode only when you need to redesign or re-sequence work.

## 5) Separate Copy/Paste Prompts For New Codex Chats

### Prompt A — Finish Phase 5

```text
You are continuing implementation in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Goal: Complete remaining Phase 5 tasks from docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md.

Current truth:
- Phase 5 already done: gold examples injection + 5000-char cap.
- Unwired modules exist: src/feedops/pipeline/keyword_gaps.py and src/feedops/pipeline/competitor_evidence.py
- Need runtime integration into src/feedops/pipeline/evidence.py

Required tasks:
1) Wire keyword gaps into evidence assembly.
2) Wire competitor evidence into evidence assembly with strict no-speculative-claims behavior.
3) Add integration tests:
   - keyword gaps are category-relevant and finish-excluded
   - competitor evidence never emits unverifiable/better-than language
4) Update docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md execution log after each task.
5) Run verification:
   - .venv/bin/pytest -q
   - RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

Constraints:
- Python is runtime prompt source of truth.
- Supabase prompt_templates.system_prompt must not override runtime prompt.
- Google description cap is 5000.
- Keep changes focused; no unrelated refactors.
```

### Prompt B — Implement Phase 6

```text
Implement Phase 6 from docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Scope:
- Dashboard production readiness only.
- Idempotent regeneration/review/publish states.
- Batch safety and actionable failure states.
- Validation errors surfaced clearly in UI/API.

Required workflow:
1) Inspect current Phase 6 section and convert each bullet into executable subtasks.
2) Implement one subtask at a time with tests.
3) After each task, update execution log in the master plan immediately.
4) Run verification after each major change:
   - cd dashboard && npm run lint && npm run build
   - relevant python/api tests
5) End with a summary of completed Phase 6 items and any deferred risks.

Constraints:
- Keep Python runtime as generation authority.
- No prompt-source rework in this phase unless required for bugfix.
```

### Prompt C — Implement Phase 7

```text
Implement Phase 7 (observability/reliability/performance) from docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md.

Deliverables:
- Structured logs with request IDs across generation path.
- Metrics for latency, retry rates, validation failures, provider errors.
- Provider backoff/circuit-breaker hardening.
- Kill switch config for generation/finish-sentence paths.

Execution rules:
1) Add tests for each reliability feature.
2) Keep toggles documented and safe-by-default.
3) Update execution log in master plan after each task.
4) Run:
   - .venv/bin/pytest -q
   - RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh
```

### Prompt D — Implement Phase 8

```text
Implement Phase 8 (72k scale-up runbook) from docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md.

Deliverables:
- Concrete batch sizing strategy.
- Operator runbook for generate -> review -> publish.
- Stop-condition thresholds and rollback instructions.
- Dry-run and spot-check verification commands.

Execution rules:
1) Create/update docs with exact commands and expected outcomes.
2) Ensure runbook aligns with current code paths and tables.
3) Update execution log in master plan when each runbook block is finalized.
4) Validate all commands listed in the runbook at least once in this environment.
```

### Prompt E — Browser E2E + Single-SKU Quality/SOT Validation

```text
You are validating the production dashboard and Python generation authority in /Users/bobby/Documents/GitHub/Allied-FeedOps.

Goal:
- Fully exercise the dashboard with browser automation.
- Regenerate content for at least one real SKU.
- Verify Python single-source-of-truth methodology is actually driving output quality and traceability.

Required tools/workflow:
- Use agent-browser for web automation:
  1) agent-browser open <url>
  2) agent-browser snapshot -i
  3) agent-browser click/fill using @e refs
  4) re-snapshot after every state change

Execution steps:
1) Start required services (if not already running) and capture exact URLs used.
2) Browser-test these dashboard flows end-to-end:
   - Login/access dashboard
   - SKU selection / generate flow
   - Regenerate flow with and without feedback
   - Batch and publish-readiness screens (including failure/remediation visibility)
3) For one concrete SKU, run generation and collect evidence:
   - generated title + description outputs (google/bing/shopify where available)
   - prompt hash and model metadata persisted by Python pipeline
   - finish sentence behavior (enabled/disabled path if applicable)
4) Verify Python single source of truth:
   - Confirm generated outputs map to Python canonical prompt/hash path (not dashboard-local prompt drift)
   - Confirm traceability fields in DB/API responses are consistent
5) Quality review for that SKU output:
   - factuality/evidence grounding
   - keyword placement quality
   - policy guardrails (no prohibited stuffing/claims)
   - concise scorecard with pass/fail and specific issues
6) Summarize findings:
   - What passed
   - What failed
   - Severity + exact repro steps
   - Recommended fixes (ranked)
7) Update docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md execution log with this validation run and result.

Verification commands to run and report:
- .venv/bin/pytest -q
- RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh

Constraints:
- Do not change prompt-source architecture in this validation task.
- Keep evidence concrete: include SKU, route touched, and stored metadata fields used to validate SOT.
```

## 6) Immediate Next Command (if continuing in this chat)

- `git status`
- Recommended next: run Prompt E now (pre-Phase 8 UAT gate), then Prompt D (Phase 8 runbook), then Prompt E again as post-Phase-8 confirmation.
