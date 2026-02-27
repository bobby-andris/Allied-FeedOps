# Generation Quality Phase Kickoff (Post-PlanFix)

## Purpose
Start the next optimization phase for title/description quality from a clean, deterministic baseline on current `master`.

This document uses:
1. Current runtime architecture in `docs/architecture/2026-02-26-prompt-source-and-generation-flow.md`.
2. v1.3a phase learnings in `.planning/milestones/v1.3a-phases`.
3. Strategic goals in `docs/plans/2026-02-21-strategic-milestone-assessment.md`.

## Current Baseline Assumptions

1. Regeneration is deterministic and single-writer (Python API only).
2. Async dashboard flow prevents long blocking UI calls.
3. Runtime prompt routing no longer depends on v1/v2 behavior flags.
4. Parser contract is strict for required keys (no silent partial success).
5. Cloud Run parity checks are mandatory pre-merge.

## v1.3a Recurring Failure Patterns And Remediations

| Pattern observed in v1.3a | Root issue | Deterministic remediation (current phase) | Gate |
|---|---|---|---|
| Template-like openings and repetitive copy | Over-constrained prompt shape + weak diversity controls | Add explicit anti-template opening constraints and diversity penalties in evaluation rubric | Distinct-opening rate >= 90% on eval corpus |
| Routing drift between intended and actual prompt path | Env-driven prompt architecture toggles + mixed authorities | Keep code-owned canonical prompt path only; no runtime behavior toggle for prompt source | Zero code paths that branch by prompt version in generation runtime |
| Harness vs runtime mismatch | Test harness normalization differed from production flow | Evaluate through current runtime-equivalent generator path and parity suites only | No evaluator path may bypass runtime normalization/parsing |
| Placeholder leakage and malformed platform output | Partial schema acceptance + weak parse enforcement | Maintain strict required-key parse failures with retries and terminal errors | Missing required keys must fail run, never persist |
| Weak differentiation and low engagement | Evidence-driven but story-light generation instructions | Expand product-specific differentiation guidance (category + collection + use-case evidence) | Human blind review win-rate >= target threshold |
| Score inflation by self-assessment | Self-score rubric too narrow in some rounds | Use independent quality scoring (`PromptEvalRecord` metrics + policy checks) for gate decisions | Composite gate based on external evaluator, not self-score alone |

## Strategic Alignment (from 2026-02-21 Assessment)

The strategic plan calls out that optimization systems are only as good as content inputs. This phase prioritizes content quality improvements that are:

1. Deterministic (same routing and persistence every run).
2. Measurable (fixed eval corpus + stable scoring).
3. Safe to roll out (policy and factual guardrails are hard gates).

## Execution Plan (Generation Quality)

### GQ-1 Baseline Measurement

1. Use fixed corpus: `samples/eval-skus-google-ads-90d.json` (or `samples/eval-skus-phase28.json` when running broader root-cause sweeps).
2. Use deterministic evaluation runner:
   - `scripts/phase28_root_cause_eval.py`
3. Store artifacts under `artifacts/prompt-quality/<run_id>/` and report in `docs/experiments/`.

### GQ-2 Prompt Quality Improvements

1. Improve opening sentence strategy by category to avoid formulaic intros.
2. Increase product-specific differentiation from evidence fields.
3. Maintain channel-specific constraints without keyword stuffing.
4. Keep finish sentence integration precise and non-generic.

### GQ-3 Contract And Telemetry Guarding

1. Keep strict schema parsing and explicit failure semantics.
2. Ensure prompt hash and request_id always flow into lineage tables.
3. Add evaluation diagnostics that do not affect user-facing copy.

### GQ-4 Rollout And Verification

1. Stage with changed vs unchanged SKU regenerate checks.
2. Validate deterministic DB behavior:
   - changed candidate -> one `generated_content` mutation + one `regeneration_history` row
   - unchanged candidate -> zero content/history writes
3. Merge only when quality gate and policy gate both pass.

## Quality Gates For This Phase

1. **Policy gate**: 0 hard policy violations.
2. **Factual gate**: 0 invented claims in sampled manual audit.
3. **Differentiation gate**: measurable lift vs baseline in product-specificity score.
4. **Engagement gate**: measurable lift vs baseline in hook/engagement metrics.
5. **Stability gate**: parity test suite green and no routing/persistence regressions.

## Baseline Runner Commands

### Dry run (no model calls)

```bash
cd /Users/bobby/.codex/worktrees/e245/Allied-FeedOps
UV_FROZEN=1 uv run --frozen --extra dev python scripts/phase28_root_cause_eval.py \
  --sample-file samples/eval-skus-google-ads-90d.json \
  --variants control \
  --platforms google,bing,shopify \
  --replicates 1 \
  --dry-run
```

### Baseline run

```bash
cd /Users/bobby/.codex/worktrees/e245/Allied-FeedOps
bash scripts/run_generation_quality_baseline.sh
```

## Deliverables

1. Baseline artifacts (`records.jsonl`, `summary.csv`) for the fixed corpus.
2. Baseline quality report in `docs/experiments/`.
3. Prompt iteration plan with explicit hypothesis per change.
4. Before/after quality deltas and merge recommendation.

## Out of Scope For This Phase

1. Reintroducing prompt version behavior toggles.
2. Changing deployment topology.
3. Reworking persistence contract semantics.

These are now considered platform invariants and should remain stable while quality iteration proceeds.
