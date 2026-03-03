# Query-Intent Feed Optimizer V1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a deterministic query-intent brief to Google/Bing generation prompts without changing task models, public routes, or prompt-lineage guarantees.

**Architecture:** Build a Python-runtime-owned `QueryIntentBrief` from live search-query evidence, compute it once per generation bundle, inject it into eligible Google/Bing user prompts behind a feature flag, and record its presence through existing lineage fields and diagnostics. Keep the implementation additive, bounded, and self-disabling when data is weak.

**Tech Stack:** Python, FastAPI pipeline runtime, Supabase-backed evidence queries, pytest, existing prompt-builder and lineage infrastructure.

---

### Task 1: Planning Artifacts

**Files:**
- Create: `docs/plans/2026-03-01-query-intent-feed-optimizer-design.md`
- Create: `docs/plans/2026-03-01-query-intent-feed-optimizer-implementation-plan.md`

**Step 1: Write the design doc**

Document the problem, business hypothesis, data sources, prompt assembly plan, invariants, persistence impact, rollout, and verification requirements.

**Step 2: Save the implementation plan**

Capture the concrete file/test/verification sequence used below.

### Task 2: Feature Flag Support

**Files:**
- Modify: `src/feedops/pipeline/feature_flags.py`
- Test: `tests/test_query_intent_brief.py`

**Step 1: Write the failing feature-flag test**

Verify `QUERY_INTENT_BRIEF_V1` defaults to disabled/enabled exactly as intended and appears in `capture_flag_snapshot()`.

**Step 2: Run the test to verify failure**

Run:

```bash
pytest tests/test_query_intent_brief.py -k feature_flag -v
```

**Step 3: Implement the flag**

Add:

- `is_query_intent_brief_v1_enabled()`
- `QUERY_INTENT_BRIEF_V1` in `capture_flag_snapshot()`

**Step 4: Run the targeted test**

Re-run the same pytest command and confirm it passes.

### Task 3: QueryIntentBrief Builder

**Files:**
- Create: `src/feedops/pipeline/query_intent_brief.py`
- Test: `tests/test_query_intent_brief.py`

**Step 1: Write failing builder tests**

Cover:

- strong query rows create a bounded brief
- competitor/noise terms are excluded
- unsupported attributes are excluded
- weak data disables the brief
- ordering is deterministic
- finish-heavy noise does not leak into base Google/Bing emphasis

**Step 2: Run the builder tests to verify failure**

Run:

```bash
pytest tests/test_query_intent_brief.py -v
```

**Step 3: Implement the minimal builder**

Create:

- `QueryIntentBrief`
- `QueryIntentDiagnostics`
- formatter/helper for prompt section output

Use existing curation helpers and business-weighted ranking. Keep the output bounded and additive only.

**Step 4: Run the builder tests**

Re-run:

```bash
pytest tests/test_query_intent_brief.py -v
```

### Task 4: Prompt Builder Injection

**Files:**
- Modify: `src/feedops/api/prompt_builder.py`
- Modify: `src/feedops/generation/tasks.py`
- Test: `tests/test_query_intent_prompt_builder.py`

**Step 1: Write failing prompt assembly tests**

Verify:

- Google title/description include `<query_intent_brief>` when enabled and sufficient
- Bing title/description include it too
- Shopify does not
- finish prompt does not
- disabled path preserves current behavior

**Step 2: Run the prompt tests to verify failure**

Run:

```bash
pytest tests/test_query_intent_prompt_builder.py -v
```

**Step 3: Implement prompt threading**

Add internal-only optional arguments:

- `build_task_prompt(..., query_intent_context=None)`
- `build_core_prompt(..., query_intent_section=None, query_intent_diagnostics=None)` or equivalent

Inject the section only for Google/Bing title/description prompts and place it after keyword hints and before shopping intelligence/category guidance.

**Step 4: Run the prompt tests**

Re-run:

```bash
pytest tests/test_query_intent_prompt_builder.py -v
```

### Task 5: Compute Brief Once Per Execution Bundle

**Files:**
- Modify: `src/feedops/generation/executor.py`
- Test: `tests/test_query_intent_executor_integration.py`

**Step 1: Write failing executor integration tests**

Verify:

- brief is computed once per bundle
- only eligible Google/Bing tasks receive it
- no extra task kinds or provider calls are introduced

**Step 2: Run the executor tests to verify failure**

Run:

```bash
pytest tests/test_query_intent_executor_integration.py -v
```

**Step 3: Implement bundle-scoped computation**

Compute the brief after evidence is built, pass it into task prompt construction, and preserve current task spec resolution untouched.

**Step 4: Run the executor tests**

Re-run:

```bash
pytest tests/test_query_intent_executor_integration.py -v
```

### Task 6: Lineage Diagnostics

**Files:**
- Modify: `src/feedops/api/main.py`
- Test: `tests/test_query_intent_lineage.py`

**Step 1: Write failing lineage tests**

Verify:

- `user_prompt` contains the brief when enabled
- `QUERY_INTENT_BRIEF_V1` persists in feature flags
- diagnostics fields persist in generation diagnostics

**Step 2: Run the lineage tests to verify failure**

Run:

```bash
pytest tests/test_query_intent_lineage.py -v
```

**Step 3: Implement diagnostics propagation**

Use existing `generation_diagnostics` support; do not add schema changes.

**Step 4: Run the lineage tests**

Re-run:

```bash
pytest tests/test_query_intent_lineage.py -v
```

### Task 7: Task-Model Regression Protection

**Files:**
- Modify: `tests/test_generation_runtime_scope_contract.py`
- Modify: `tests/test_hybrid_generation_parity.py`
- Modify only if needed: `tests/api/test_hybrid_generation_telemetry_contract.py`

**Step 1: Add regression assertions**

Verify the feature does not:

- add extra task kinds
- add extra provider-backed calls
- widen title-only or description-only execution scope

**Step 2: Run the targeted regression suite**

Run:

```bash
pytest tests/test_generation_runtime_scope_contract.py tests/test_hybrid_generation_parity.py tests/api/test_hybrid_generation_telemetry_contract.py -v
```

**Step 3: Adjust implementation only if a regression is proven**

Keep the task graph unchanged.

### Task 8: Wider Regression Suite

**Files:**
- No new files required beyond prior tasks

**Step 1: Run the required host suites**

Run:

```bash
pytest \
  tests/test_query_intent_brief.py \
  tests/test_query_intent_prompt_builder.py \
  tests/test_query_intent_executor_integration.py \
  tests/test_query_intent_lineage.py \
  tests/test_generation_runtime_scope_contract.py \
  tests/test_hybrid_generation_parity.py \
  tests/api/test_hybrid_generation_telemetry_contract.py \
  tests/test_cloud_run_parity.py \
  tests/test_runtime_env_contract.py \
  tests/test_env_parity.py \
  tests/test_prompt_sanitization_contract.py \
  tests/test_keyword_placement.py \
  tests/test_search_query_hygiene.py -v
```

**Step 2: Fix only proven failures**

If anything fails, keep the changes narrow and preserve the original feature boundaries.

### Task 9: Evaluation Artifact Prep

**Files:**
- Create or modify: `docs/experiments/2026-03-01-query-intent-feed-optimizer/report.md`
- Optional artifacts under a sibling experiment artifacts directory

**Step 1: Capture before/after prompt traces and rubric notes**

Use:

- `samples/eval-skus-google-ads-90d.json`
- `samples/eval-skus.json`

**Step 2: Record evaluation criteria**

Track:

- factual accuracy
- platform compliance
- keyword naturalness
- customer readability
- style consistency
- placeholder correctness
- query relevance
- likely paid-performance usefulness

### Task 10: Runtime Verification

**Files:**
- Update: `docs/experiments/2026-03-01-query-intent-feed-optimizer/report.md`

**Step 1: Run local container smoke**

Run:

```bash
ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh
```

**Step 2: If certification proceeds, verify deployed runtime**

Capture:

- Cloud Run revision
- request IDs
- job IDs where applicable
- prompt lineage rows
- dashboard readback evidence

**Step 3: Record GO / NO-GO**

Do not claim completion without fresh evidence from host tests and runtime verification.
